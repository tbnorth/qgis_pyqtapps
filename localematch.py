from qgis.core import *
from qgis.gui import *
from PyQt4 import QtGui
from PyQt4.QtCore import Qt
import psycopg2

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
                'name': "a_locale",
                'schema': "glei_1_orig",
                'table': "a_locale",
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
        
        self.pnt_ids = self.map_attr_to_id('points', 'seg_hash')
        QgsMessageLog.logMessage("%d locale point sets loaded"%len(self.pnt_ids))

        self.site_ids = self.map_attr_to_id('sites', 'site')
        QgsMessageLog.logMessage("%d sites loaded"%len(self.site_ids))    

        self.locale_ids = self.map_attr_to_id('a_locale', 
            key=lambda f: (int(f['seg_num']), int(f['poly_num'])))
        QgsMessageLog.logMessage("%d locales loaded"%len(self.locale_ids))    
        QgsMessageLog.logMessage(str(self.locale_ids.keys()))    

        con = psycopg2.connect(self.uri.connectionInfo())
        cur = con.cursor()

        cur.execute("""
        create temp table albsite as
        select site, st_transform(simp_geom, 96703) as simp_geom
          from glrimon.site
        ;
        create index faster on albsite using gist (simp_geom)
        ;
        create temp table mcp as
        select seg_hash, 
               ST_ConvexHull(ST_Collect(wkb_geometry)) as geom, 
               ST_buffer(ST_ConvexHull(ST_Collect(wkb_geometry)),3000) as buffed
          from glei_1_shape.a_point
         where seg_hash is not null and seg_hash > 0
         group by seg_hash
        ;
        create index faster2 on mcp using gist (geom)
        ;
        create temp table sh2s as
        select seg_hash, site, 0::float as sep
          from albsite, mcp
         where ST_Intersects(simp_geom, buffed)
        ;
        update sh2s
           set sep = ST_Distance(simp_geom, geom)
          from mcp, albsite
         where sh2s.seg_hash = mcp.seg_hash and
               sh2s.site = albsite.site
        ;
        select * from sh2s order by seg_hash, sep;
        """)
        
        self.sh2s = {}
        for sh, site, sep in cur.fetchall():
            self.sh2s.setdefault(sh, []).append((site, sep))
            
        cur.execute("select trim(code), name from glei_1_orig.a_subproject_desc")
        self.sp2name = dict(cur.fetchall())
        cur.execute("select trim(code), name from glei_1_orig.a_geomorph_desc")
        self.geo2name = dict(cur.fetchall())
        
           
        """
        -- sampled locales with not points / poly
        SELECT distinct seg_num, poly_num 
          from glei_1_orig.a_locale where status = 'S' and 
               not exists (select 1 from glei_1_shape.a_point 
                            where a_point.seg_num = a_locale.seg_num and 
                                  a_point.poly_num = a_locale.poly_num ) and 
               -- not -- uncomment for no poly and no points 
               exists (select 1 from glei_1_shape.a_locale as loc 
                            where loc.seg_num = a_locale.seg_num and 
                                  loc.poly_num = a_locale.poly_num ) 
         order by seg_num, poly_num
        ;
        

        """
           
    def close(self):
        mb = self.iface.messageBar()
        mb.pushWidget(mb.createMessage("GONE"))
        self.deleteLater()   
    def nextThing(self):
        iface = self.iface
        canvas = iface.mapCanvas()
        
        w = self.options
        if 0:
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
            
        notes = QtGui.QTextEdit()
        w.layout().addWidget(notes)
        
        sh = sorted(self.sh2s)[0]
        points = self.layers()['points']
        points.removeSelection()
        points.select(self.pnt_ids[sh])
        self.iface.setActiveLayer(points)
        canvas.zoomToSelected(points)
        canvas.zoomByFactor(1.5)

        sites = self.layers()['sites']
        sites.removeSelection()

        def say(text, notes=notes):
            notes.setDocument(QtGui.QTextDocument(
                (notes.toPlainText()+'\n'+text).strip()
            ))
        
        say("Locale %s"%sh)
        
        near_sites = self.sh2s.get(sh, [])
        if not near_sites:
            say("NO NEARBY SITES")
            
        locales = self.layers()['a_locale']
        seg_num = int(sh / 1000)
        poly_num = int(sh - seg_num * 1000)
        lfid = self.locale_ids[(seg_num, poly_num)][0]
        lfr = QgsFeatureRequest(lfid)
        lfr.setFlags(QgsFeatureRequest.NoGeometry)
        locale = next(locales.getFeatures(lfr))
        sub = self.sp2name[locale['subproject']]
        geo = self.geo2name[locale['geomorph']]
        say("%s %s sampling" % (sub, geo))
            
        def show_site(site, self=self):
            sites = self.layers()['sites']
            self.iface.setActiveLayer(sites)
            sites.removeSelection()
            sites.select(self.site_ids[site])
            self.iface.mapCanvas().panToSelected(sites)

        for site, sep in near_sites:
            lvls = QtGui.QWidget()
            lvls.setLayout(QtGui.QHBoxLayout())
            w.layout().addWidget(lvls)
            lo = lvls.layout()
            but = QtGui.QPushButton(str(site))
            
            but.clicked.connect(lambda checked, site=site: show_site(site))
            lo.addWidget(but)
            bg = QtGui.QButtonGroup()
            lo.bg = bg
            for s in 'strong', 'ok', 'weak', 'none':
                but = QtGui.QPushButton(s)
                but.setCheckable(True)
                but.setStyleSheet("QPushButton::checked { background: green }")
                but.sh = sh
                but.site = site
                but.level = s
                if s == 'none':
                    but.setChecked(True)
                bg.addButton(but)
                lo.addWidget(but)
            lo.addStretch()
            
        but = QtGui.QPushButton("Mark data as assigned")
        but.setCheckable(True)
        but.setObjectName("assigned")
        but.setStyleSheet("QPushButton::checked { background: green }")
        
        w.layout().addStretch()

        return
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
        
        

