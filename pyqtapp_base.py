"""
"""
from qgis.core import *
from qgis.gui import *
from PyQt4 import QtGui
from PyQt4.QtCore import Qt

import time
import os

class Dock(QtGui.QDockWidget):
    def __init__(self, panel):
        title = panel.dock_name()
        QtGui.QDockWidget.__init__(self, title)
        self.setWidget(panel)

        # fixme not really working
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
        uri.setConnection("beaver.nrri.umn.edu", "5432", "nrgisl01", "tbrown", "frogspit")
        uri.setConnection("127.0.0.1", "15432", "nrgisl01", "tbrown", "frogspit")
     
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
                QgsMapLayerRegistry.instance().addMapLayer(layer)

    @staticmethod
    def do_run_script(iface, Panel):
        """Run this class in the QGIS UI"""    
        
        panel = Panel(iface)

        dock = Dock(panel)

        main = iface.mainWindow()
        
        main.addDockWidget(Qt.RightDockWidgetArea, dock)
    def map_attr_to_id(self, layer_name, attr_name=None, key=None):
        ans = {}
        fr = QgsFeatureRequest()
        fr.setFlags(QgsFeatureRequest.NoGeometry)
        for i in self.layers()[layer_name].getFeatures(fr):
            if key:
                keyval = key(i)
            else:
                keyval = i[attr_name]
            ans.setdefault(keyval, []).append(i.id())
        return ans
