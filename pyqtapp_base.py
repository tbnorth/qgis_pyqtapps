"""
"""
from qgis.core import *
from qgis.gui import *
from PyQt4 import QtGui
from PyQt4.QtCore import Qt

import time
import os

def run_script(iface):
       
    print "\n\n--START-- %s -----------------------\n" % time.asctime()

    Panel.run_script(iface)
    
    print "\n--END---- %s -----------------------" % time.asctime()
    
class Dock(QtGui.QDockWidget):
    def __init__(self, panel):
        title = panel.dock_name()
        QtGui.QDockWidget.__init__(self, title)
        self.setWidget(panel)
        self.visibilityChanged.connect(self.check_closed)
        self.destroyed.connect(self.check_closed)
    def check_closed(self, visible=False):
        mb = QtGui.QMessageBox()
        mb.setText("thinking")
        mb.exec_()
        if not visible:
            mb.setText("thunk")
            mb.exec_()
            self.getWidget().close()
            self.deleteLater() 
    def close(self):
        mb = QtGui.QMessageBox()
        mb.setText("thinking about closing")
        lmb.exec_()
        if not visible:
            self.getWidget().close()
            self.deleteLater() 
class IfaceUser:
    def layers(self):
        """return dict of layers keyed by name
        http://gis.stackexchange.com/questions/26257/how-can-i-iterate-over-map-layers-in-qgis-python
        iface.mapCanvas().layers() gives nothing, .mapLayers() gives
        a dict with unhelpful keys, so use .legendInterface().layers()
        """
        return dict([(i.name(), i) for i in 
            self.iface.legendInterface().layers()])

    def load_layers(self, layers):
        """Load layers from list of dicts of form::
            
            {
                'name': "complexes",
                'schema': "glei_1_shape",
                'table': "a_complex",
                'geom_col': "wkb_geometry",  # OPTIONAL
                'CRS': 5070,  # OPTIONAL
                'provider': "postgres",  # OPTIONAL
            },
            
            FIXME - extend to handle non-postgres providers
        """
                    
        iface = self.iface
        self.uri = uri = QgsDataSourceURI()
        uri.setConnection("127.0.0.1", "15432", "nrgisl01", "tbrown", "frogspit")
        uri.setConnection("beaver.nrri.umn.edu", "5432", "nrgisl01", "tbrown", "frogspit")
     
        for defn in layers:
            if defn['name'] not in self.layers():
                uri.setDataSource(defn['schema'], defn['table'],
                    defn.get('geom_col'))
                # FIXME, this prompts for CRS preemptively
                layer = QgsVectorLayer(
                    uri.uri(), defn['name'],
                    defn.get('provider', "postgres")
                )
                CRS = defn.get('CRS')
                if CRS:
                    layer.setCrs(QgsCoordinateReferenceSystem(CRS))
                    print 'set', QgsCoordinateReferenceSystem(CRS)
                QgsMapLayerRegistry.instance().addMapLayer(layer)

    @staticmethod
    def run_script(iface):
        """Run this class in the QGIS UI"""    
        
        panel = Panel(iface)

        dock = Dock(panel)

        main = iface.mainWindow()
        
        main.addDockWidget(Qt.RightDockWidgetArea, dock)
class Panel(QtGui.QWidget, IfaceUser):

    def __init__(self, iface):
        self.iface = iface
        QtGui.QWidget.__init__(self)
        
        self.setup_env()
        
        self.build_ui()
        
        self.layer = self.layers()['complexes']
        self.features = self.layer.getFeatures()
        
    def build_ui(self):
        self.setLayout(QtGui.QVBoxLayout())
        but = QtGui.QPushButton('Next', self)
        self.layout().addWidget(but)
        but.clicked.connect(lambda checked:self.nextThing())
        self.options = QtGui.QWidget()
        self.options.setLayout(QtGui.QVBoxLayout())
        self.layout().addWidget(self.options)
    def dock_name(self):
        """dock_name - Return name for this app
        """

        return "Complex matcher"
    def setup_env(self):
           
        self.load_layers([
            {
                'name': "complex_to_site",
                'schema': "glrig2_misc",
                'table': "complex_to_site",
            },
            {
                'name': "sites",
                'schema': "glrimon",
                'table': "site",
                'geom_col': "simp_geom",
            },
            {
                'name': "complexes",
                'schema': "glei_1_shape",
                'table': "a_complex",
                'geom_col': "wkb_geometry",
                'CRS': 5070,
            },
            {
                'name': "points",
                'schema': "glei_1_shape",
                'table': "a_point",
                'geom_col': "wkb_geometry",
                'CRS': 5070,
            },
        ])
        
    def close(self):
        mb = self.iface.messageBar()
        mb.pushWidget(mb.createMessage("GONE"))
        self.deleteLater()   
    def nextThing(self):
        iface = self.iface
        canvas = iface.mapCanvas()
        
        w = self.options
        
        for check in w.findChildren(QtGui.QCheckBox):
            print check.complex, check.site, check.isChecked()
            self.cur.execute("""update glrig2_misc.complex_to_site
               set best = %s where complex = %s and site = %s""",
               [check.isChecked(), check.complex, check.site])
            self.con.commit()
        
        cull = w.layout().takeAt(0)
        while cull:
            if cull.widget():
                cull.widget().deleteLater()
            cull = w.layout().takeAt(0)        

        self.cur.execute("""select complex, site, distance_m
             from glrig2_misc.complex_to_site
            where best is null order by complex, distance_m""")
        res = self.cur.fetchall()
            
        complex = res[0][0]
        w.layout().addWidget(QtGui.QLabel("Complex %d" % complex))
        
        for i in self.layers()['complexes'].getFeatures():
            if i.attributes()[1] == complex:
                id_ = i.id()
                break
        else:
            raise Exception("No complex %d"%complex)

        self.layer.removeSelection()
        self.layer.select(id_)
        canvas.panToSelected(self.layer)
        
        i = 0
        while res[i][0] == complex:
            cb = QtGui.QWidget()
            cb.setLayout(QtGui.QHBoxLayout())
            w.layout().addWidget(cb)
            site, distance = res[i][1], res[i][2]
            check = QtGui.QCheckBox("Site %d out by %f" % 
                (site, distance))
            check.complex = complex
            check.site = site
            cb.layout().addWidget(check)
            cb.layout().addStretch()
            check.clicked.connect(
                lambda checked, site=site: self.highlight_site(site))
            i += 1
            
        w.layout().addStretch()
        
    def highlight_site(self, site):
        
        return  # too slow
        
        sites = self.layers()['sites']

        for i in sites.getFeatures():
            if i.attributes()[0] == site:
                id_ = i.id()
                break
        else:
            raise Exception("No site %d"%site)
        sites.removeSelection()
        sites.select(id_)
        
        

