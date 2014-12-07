# -*- coding: utf-8 -*-

#system
import numpy as np

#Qt
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QTimer, QThread, pyqtSignal

#pyqtgraph
import pyqtgraph as pg
import pyqtgraph.dockarea

#vtk
from vtk.qt4.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

#own
import settings as st
from sim_core import Simulator
from sim_interface import SimulatorInteractor, SimulatorView
from model import BallBeamModel
from trajectory import HarmonicTrajectory, FixedPointTrajectory
from controller import PController, FController, GController, JController, LSSController, IOLController
from visualization import VtkVisualizer
from sensor import DeadTimeSensor

class BallBeamGui(QtGui.QMainWindow):
    '''
    class for the graphical user interface
    '''

    runSimulation = pyqtSignal()
    playbackTimeChanged = pyqtSignal()
    
    def __init__(self):
        # constructor of the base class
        QtGui.QMainWindow.__init__(self)

        # Create Simulation Backend
        self.sim = SimulatorInteractor(self)
        self.runSimulation.connect(self.sim.runSimulation)
        self.sim.simulationFinished.connect(self.simulationFinished)
        self.sim.simulationFailed.connect(self.simulationFailed)

        # sim setup viewer
        self.targetView = SimulatorView(self)
        self.targetView.setModel(self.sim.target_model)
        self.targetView.setColumnWidth(1, 100)
        self.targetView.expanded.connect(self.targetViewChanged)
        self.targetView.collapsed.connect(self.targetViewChanged)

        # sim results viewer
        self.resultview = QtGui.QTreeView()

        # dockarea allows to rearrange the user interface at runtime
        self.area = pg.dockarea.DockArea()
        
        # Window properties
        self.setCentralWidget(self.area)
        self.resize(1000, 700)
        self.setWindowTitle('Ball and Beam')
        self.setWindowIcon(QtGui.QIcon('data/ball_and_beam.png'))
        
        # create docks
        self.propertyDock = pg.dockarea.Dock('Properties', size=(1, 100))
        self.vtkDock = pg.dockarea.Dock('Simulation')
        self.dataDock = pg.dockarea.Dock('Data')
        self.plotDocks = []
        self.plotDocks.append(pg.dockarea.Dock('Placeholder'))
        
        # arrange docks
        self.area.addDock(self.vtkDock, 'right')
        self.area.addDock(self.propertyDock, 'left', self.vtkDock)
        self.area.addDock(self.dataDock, 'bottom', self.propertyDock)
        self.area.addDock(self.plotDocks[-1], 'bottom', self.vtkDock)
        
        # add widgets to the docks
        self.propertyDock.addWidget(self.targetView)        
        
        #create model for display
        self.model = BallBeamModel()

        # vtk window
        self.vtkLayout = QtGui.QVBoxLayout()
        self.frame = QtGui.QFrame()
        self.vtkWidget = QVTKRenderWindowInteractor(self.frame)
        self.vtkLayout.addWidget(self.vtkWidget)
        self.frame.setLayout(self.vtkLayout)
        self.vtkDock.addWidget(self.frame)
        self.visualizer = VtkVisualizer(self.vtkWidget)

        #data window
        self.dataList = QtGui.QListWidget(self)
        self.dataDock.addWidget(self.dataList)
        self.dataList.itemDoubleClicked.connect(self.createPlot)
        
        # action for simulation control
        self.actSimulate = QtGui.QAction(self)
        self.actSimulate.setText('Simulate')
        self.actSimulate.setIcon(QtGui.QIcon('data/simulate.png'))
        self.actSimulate.triggered.connect(self.startSimulation)
        
        # actions for animation control
        self.actPlayPause = QtGui.QAction(self)
        self.actPlayPause.setText('Play')
        self.actPlayPause.setIcon(QtGui.QIcon('data/play.png'))
        self.actPlayPause.setDisabled(True)
        self.actPlayPause.triggered.connect(self.playAnimation)

        self.actStop = QtGui.QAction(self)
        self.actStop.setText('Stop')
        self.actStop.setIcon(QtGui.QIcon('data/stop.png'))
        self.actStop.setDisabled(True)
        self.actStop.triggered.connect(self.stopAnimation)

        self.speedDial = QtGui.QDial()
        self.speedDial.setDisabled(True)
        self.speedDial.setMinimum(0)
        self.speedDial.setMaximum(100)
        self.speedDial.setValue(50)
        self.speedDial.setSingleStep(1)
        self.speedDial.resize(24, 24)
        self.speedDial.valueChanged.connect(self.updatePlaybackGain)

        self.timeSlider = QtGui.QSlider(QtCore.Qt.Horizontal, self)
        self.timeSlider.setMinimum(0)
        self.timeSliderRange = 1000
        self.timeSlider.setMaximum(self.timeSliderRange)
        self.timeSlider.setTickInterval(1)
        self.timeSlider.setTracking(True)
        self.timeSlider.valueChanged.connect(self.updatePlaybackTime)

        self.playbackTime = 0
        self.playbackGain = 1
        self.playbackTimer = QTimer()
        self.playbackTimer.timeout.connect(self.incrementPlaybackTime)
        self.playbackTimeChanged.connect(self.updateGui)
        
        # toolbar for control
        self.toolbarSim = QtGui.QToolBar('Simulation')
        self.toolbarSim.setIconSize(QtCore.QSize(24,24))
        self.addToolBar(self.toolbarSim)
        self.toolbarSim.addAction(self.actSimulate)
        self.toolbarSim.addSeparator()
        self.toolbarSim.addAction(self.actPlayPause)
        self.toolbarSim.addAction(self.actStop)
        self.toolbarSim.addWidget(self.speedDial)
        self.toolbarSim.addWidget(self.timeSlider)

    def playAnimation(self):
        '''
        play the animation
        '''
        print 'Gui(): playing animation'
        self.actPlayPause.setText('Pause')
        self.actPlayPause.setIcon(QtGui.QIcon('data/pause.png'))
        self.actPlayPause.triggered.disconnect(self.playAnimation)
        self.actPlayPause.triggered.connect(self.pauseAnimation)
        self.playbackTimer.start(0.2)
                
    def pauseAnimation(self):
        '''
        pause the animation
        '''
        print 'Gui(): pausing animation'
        self.playbackTimer.stop()
        self.actPlayPause.setText('Play')
        self.actPlayPause.setIcon(QtGui.QIcon('data/play.png'))
        self.actPlayPause.triggered.disconnect(self.pauseAnimation)
        self.actPlayPause.triggered.connect(self.playAnimation)
        
    def stopAnimation(self):
        '''
        pause the animation
        '''
        print 'Gui(): stopping animation'
        if self.actPlayPause.text() == 'Pause':
            #animation is playing -> stop it
            self.playbackTimer.stop()
            self.actPlayPause.setText('Play')
            self.actPlayPause.setIcon(QtGui.QIcon('data/play.png'))
            self.actPlayPause.triggered.disconnect(self.pauseAnimation)
            self.actPlayPause.triggered.connect(self.playAnimation)

        self.timeSlider.setValue(0)

    def startSimulation(self):
        '''
        start the simulation and disable start bottom
        '''
        print 'Gui(): launching simulation'
        self.actSimulate.setDisabled(True)
        self.runSimulation.emit()

    def simulationFinished(self, data):
        '''
        integration finished, enable play button and update plots
        '''
        print 'Gui(): simulation finished'
        self.actSimulate.setDisabled(False)
        self.actPlayPause.setDisabled(False)
        self.actStop.setDisabled(False)
        self.speedDial.setDisabled(False)
        self.timeSlider.triggerAction(QtGui.QAbstractSlider.SliderToMinimum)

        self.currentDataset = data
        self._readResults()
        self._updateDataList()
        self._updatePlots()

        self.stopAnimation()
        self.playAnimation()

    def simulationFailed(self, data):
        '''
        integration failed, enable play button and update plots
        #TODO write warning window
        '''
        print 'Gui(): simulation failed'
        box = QtGui.QMessageBox()
        box.setText('The timestep integration failed!')
        box.exec_()
        self.simulationFinished(data)

    def _readResults(self):
        self.currentStepSize = self.currentDataset['modules']['solver']['step size']
        self.currentEndTime = self.currentDataset['modules']['solver']['end time']
        self.validData = True


    
    def addPlotToDock(self, plotWidget):
        self.d3.addWidget(plotWidget)
    
    def incrementPlaybackTime(self):
        '''
        go one step forward in playback
        '''
        if self.playbackTime + self.currentStepSize*self.playbackGain \
                <= self.currentEndTime:
            self.playbackTime += self.currentStepSize*self.playbackGain
            pos = self.playbackTime / self.currentEndTime * self.timeSliderRange
            self.timeSlider.blockSignals(True)
            self.timeSlider.setValue(pos)
            self.timeSlider.blockSignals(False)
            self.playbackTimeChanged.emit()
        else:
            self.pauseAnimation()
            return

    def updatePlaybackGain(self, val):
        '''
        adjust playback time to slider value
        '''
        self.playbackGain = 10**(   \
                10.0*(val - self.speedDial.maximum()/2)/self.speedDial.maximum() \
                )

    def updatePlaybackTime(self):
        '''
        adjust playback time to slider value
        '''
        self.playbackTime = 1.0*self.timeSlider.value()/self.timeSliderRange * self.currentEndTime
        self.playbackTimeChanged.emit()
        return

    def updateGui(self):
        if not self.validData:
            return

        #update time cursor in plots
        #TODO

        #update state of rendering
        state = [self.interpolate(self.currentDataset['results']['model_output.'+str(i)]) \
                for i in range(self.model.getOutputDimension())]
        r_beam, T_beam, r_ball, T_ball = self.model.calcPositions(state)
        self.visualizer.updateScene(r_beam, T_beam, r_ball, T_ball)

    def interpolate(self, data):
        #find corresponding index in dataset that fitts the current playback time
        #TODO implement real interpolation
        index = 0
        for elem in self.currentDataset['results']['simTime']:
            if elem > self.playbackTime:
                break
            else:
                index += 1
            
        if index >= len(data):
            return 0
        else:
            return data[index]

    def _updateDataList(self):
        self.dataList.clear()
        for key, val in self.currentDataset['results'].iteritems():
            self.dataList.insertItem(0, key)

    def createPlot(self, item):
        ''' creates a plot widget corresponding to the ListItem
        '''
        title = str(item.text())
        data = self.currentDataset['results'][title]
        dock = pg.dockarea.Dock(title)
        self.area.addDock(dock, 'above', self.plotDocks[-1])
        plot = pg.PlotWidget(title=title)
        plot.plot(self.currentDataset['results']['simTime'], data)
        dock.addWidget(plot)
        self.plotDocks.append(dock)

    def _updatePlots(self):
        '''
        plot the fresh simulation data
        '''
        for dock in self.plotDocks:
            for widget in dock.widgets:
                widget.getPlotItem().setData(self.currentDataset['results']['simTime'],
                        self.currentDataset['results'][dock.name()])

    def targetViewChanged(self, index):
        self.targetView.resizeColumnToContents(0)

class TestGui(QtGui.QMainWindow):
    
    def __init__(self):
        # constructor of the base class
        QtGui.QMainWindow.__init__(self)
        self.sim = SimulatorInteractor(self)

        #viewer
        self.targetView = SimulatorView(self)
        self.targetView.setModel(self.sim.target_model)

        # Window properties
        self.setCentralWidget(self.targetView)
        self.resize(500, 500)
        self.setWindowTitle('Sim Test')
       
