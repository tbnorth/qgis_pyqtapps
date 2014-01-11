from qgis.core import *
from qgis.gui import *
from PyQt4 import QtGui
from PyQt4.QtCore import Qt

import time
import os

import pyqtapp_base; reload(pyqtapp_base)
from pyqtapp_base import IfaceUser


def run_script(iface):
       
    print "\n\n--START-- %s -----------------------\n" % time.asctime()

    Panel.do_run_script(iface, Panel)
    
    print "\n--END---- %s -----------------------" % time.asctime()
    

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
        lyr = self.layers()['complex_to_site']
        
        # lyr.startEditing()
        
        fr = QgsFeatureRequest()
        fr.setFlags(QgsFeatureRequest.NoGeometry)
        
        to_set = {}
        for check in w.findChildren(QtGui.QCheckBox):
            to_set[(check.complex, check.site)] = check.isChecked()
            QgsMessageLog.logMessage(str((check.complex, check.site)))
        if to_set:
            QgsMessageLog.logMessage("set")
            for feature in lyr.getFeatures(fr):
                attrs = feature.attributes()
                key = tuple(attrs[:2])
                QgsMessageLog.logMessage(str(key))
                if key in to_set:
                    QgsMessageLog.logMessage("here")
                    lyr.dataProvider().changeAttributeValues({
                        feature.id(): {3: to_set[key]}
                    })
                    
        # lyr.commitChanges()
        # lyr.reload()
        
        cull = w.layout().takeAt(0)
        while cull:
            if cull.widget():
                cull.widget().deleteLater()
            cull = w.layout().takeAt(0)        

        
        


        # needs 2.1
        # fr = QgsFeatureRequest(QgsExpression("""
        #     exists (select 1 from glrig2_misc.complex_to_site x
        #             where x.complex = glrig2_misc.complex_to_site.complex
        #             and x.site = glrig2_misc.complex_to_site.site 
        #             and x.best is null)"""))    
        lyr.setSubsetString("""
            exists (select 1 from glrig2_misc.complex_to_site x
                    where x.complex = glrig2_misc.complex_to_site.complex
                    and x.site = glrig2_misc.complex_to_site.site 
                    and x.best is null)""")
                                
        fr = QgsFeatureRequest()
        
        fr.setFlags(QgsFeatureRequest.NoGeometry)
        features = lyr.getFeatures(fr)
        feature = next(features)
        
        mb = self.iface.messageBar()
        mb.pushMessage('info', "items: %d"%lyr.featureCount(), duration=6)

        attr = feature.attributes()
            
        complex = attr[0]
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
        while feature.attributes()[0] == complex:
            cb = QtGui.QWidget()
            cb.setLayout(QtGui.QHBoxLayout())
            w.layout().addWidget(cb)
            site, distance = feature.attributes()[1], feature.attributes()[2]
            check = QtGui.QCheckBox("Site %d out by %f" % 
                (site, distance))
            check.complex = complex
            check.site = site
            cb.layout().addWidget(check)
            cb.layout().addStretch()
            check.clicked.connect(
                lambda checked, site=site: self.highlight_site(site))
            try:
                feature = next(features)
            except StopIteration:
                break
            
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
        
        

