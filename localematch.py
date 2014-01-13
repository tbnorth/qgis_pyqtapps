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
        
        self.nextThing()
        
    def build_ui(self):
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().setSpacing(2)
        
        self.options = QtGui.QWidget()
        self.options.setLayout(QtGui.QVBoxLayout())
        self.options.layout().setSpacing(2)
        self.layout().addWidget(self.options)

        row = QtGui.QWidget()
        row.setLayout(QtGui.QHBoxLayout())
        self.layout().addWidget(row)
        
        but = QtGui.QPushButton('Prev', self)
        row.layout().addWidget(but)
        but.clicked.connect(lambda checked:self.nextThing(previous=True))
        
        but = QtGui.QPushButton('Next', self)
        row.layout().addWidget(but)
        but.clicked.connect(lambda checked:self.nextThing())
        
        self.jump = jump = QtGui.QComboBox()
        row.layout().addWidget(jump)
        for i in sorted(self.sh2s.keys()):
            jump.addItem(str(int(i)))
        jump.activated.connect(lambda idx, j=jump: self.nextThing(jump=j.currentText()))
        
    def dock_name(self):
        """dock_name - Return name for this app
        """

        return "Locale matcher"
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
		
        for i in 'points', 'sites', 'a_locale':
            self.layers()[i].setSubsetString('')
        
        self.pnt_ids = self.map_attr_to_id('points', 'seg_hash')
        QgsMessageLog.logMessage("%d locale point sets loaded"%len(self.pnt_ids))
        # QgsMessageLog.logMessage(str(self.pnt_ids.keys()))    

        self.site_ids = self.map_attr_to_id('sites', 'site')
        QgsMessageLog.logMessage("%d sites loaded"%len(self.site_ids))    

        self.locale_ids = self.map_attr_to_id('a_locale', 
            key=lambda f: (int(f['seg_num']), int(f['poly_num'])))
        QgsMessageLog.logMessage("%d locales loaded"%len(self.locale_ids))    
        # QgsMessageLog.logMessage(str(self.locale_ids.keys()))    

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
               -- ST_ConvexHull(ST_Collect(wkb_geometry)) as geom, 
               ST_Collect(wkb_geometry) as geom, 
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
        select sh2s.* 
          from sh2s 
               left join glrig2_misc.locale_mapped using (seg_hash)
         where status is null
        order by seg_hash, sep;
        """)
        
        self.sh2s = {}
        for sh, site, sep in cur.fetchall():
            self.sh2s.setdefault(sh, []).append((site, sep))
        self.sh_n = 0  # which one are we looking at
        # QgsMessageLog.logMessage(str(self.sh2s.keys()))   
		
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
        
        create table glrig2_misc.locale_mapped (
            seg_hash int primary key, 
            status text
        );
        
        insert into glrig2_misc.locale_mapped
        select 1000*seg_num+poly_num, 'high-energy'
          from glei_1_orig.a_locale
         where geomorph = 'He' and status = 'S';
         
        create table glrig2_misc.locale_to_site (
            seg_hash int,
            site int,
            status text
        );


        """
           
    def close(self):
        mb = self.iface.messageBar()
        mb.pushWidget(mb.createMessage("GONE"))
        self.deleteLater()   
    def nextThing(self, previous=False, jump=None):
        iface = self.iface
        canvas = iface.mapCanvas()
        
        con = psycopg2.connect(self.uri.connectionInfo())
        cur = con.cursor()
        
        w = self.options
        self.options.hide()  # shows that something's happening
        
        statii = self.options.findChildren(QtGui.QPushButton, 'status')
        for status in statii:
            if status.text() == "don't mark":
                continue
            if status.isChecked():
                print status.sh, status.text()
                cur.execute("""
                    update glrig2_misc.locale_mapped
                       set status = %s
                     where seg_hash = %s;
                    """, [status.text(), status.sh])
                cur.execute("""
                    insert into glrig2_misc.locale_mapped
                    select %s, %s
                     where not exists (select 1 from glrig2_misc.locale_mapped x
                                        where x.seg_hash = %s)
                    """, [status.sh, status.text(), status.sh])
                
        statii = self.options.findChildren(QtGui.QPushButton, 'strength')
        for status in statii:
            if status.isChecked():
                print status.sh, status.site, status.text()
                cur.execute("""
                    update glrig2_misc.locale_to_site
                       set status = %s
                     where seg_hash = %s and site = %s;
                    """, [status.text(), status.sh, status.site])
                cur.execute("""
                    insert into glrig2_misc.locale_to_site
                    select %s, %s, %s
                     where not exists (select 1 from glrig2_misc.locale_to_site x
                                        where x.seg_hash = %s and x.site = %s)
                    """, [status.sh, status.site, status.text(), 
                          status.sh, status.site])
                
        con.commit()
        
        if 0:
            lyr = self.layers()['complex_to_site']
            
            # lyr.startEditing()
          
            fr = QgsFeatureRequest()
            fr.setFlags(QgsFeatureRequest.NoGeometry)
            
            to_set = {}
            for check in self.options.findChildren(QtGui.QCheckBox):
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
            
        cull = self.options.layout().takeAt(0)
        while cull:
            if cull.widget():
                cull.widget().deleteLater()
            cull = self.options.layout().takeAt(0)  
            
        w = QtGui.QWidget()
        w.setLayout(QtGui.QVBoxLayout())
        w.layout().setSpacing(2)
            
        notes = QtGui.QTextEdit()
        w.layout().addWidget(notes)
        
        if previous:
            self.sh_n -= 2
            
        if jump:
            jump = int(jump)
            for n, i in enumerate(sorted(self.sh2s)):
                if i == jump:
                    self.sh_n = n
                    break
            else:
                raise Exception("Did not find %d"%jump)
        
        sh = sorted(self.sh2s)[self.sh_n]
        points = self.layers()['points']
        points.removeSelection()
        
        points.setSubsetString("seg_hash = %d"%sh)
        
        points.select(self.pnt_ids[sh])
        self.iface.setActiveLayer(points)
        if len(self.pnt_ids[sh]) > 1:
            canvas.zoomToSelected(points)
            canvas.zoomByFactor(3)
        else:
            canvas.panToSelected(points)

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
            
        w.layout().addWidget(QtGui.QLabel("Site, distance, strength of match"))
        cur.execute("""select site, status 
                         from glrig2_misc.locale_to_site
                        where seg_hash = %s""", [sh])
        site_status = dict(cur.fetchall())

        for site, sep in near_sites:
            lvls = QtGui.QWidget()
            lvls.setLayout(QtGui.QHBoxLayout())
            w.layout().addWidget(lvls)
            lo = lvls.layout()
            lo.setSpacing(2)
            but = QtGui.QPushButton(str(site))
            but.clicked.connect(lambda checked, site=site: show_site(site))
            lo.addWidget(but)
            lab = QtGui.QLabel(str(int(sep))+'m')
            # lab.setMinimumHeight(12)
            lab.setMinimumWidth(55)
            lab.setMaximumWidth(55)
            lo.addWidget(lab)
            bg = QtGui.QButtonGroup()
            lo.bg = bg
            picked = site_status.get(site, 'none')
            for s in 'strong', 'ok', 'weak', 'none':
                but = QtGui.QPushButton(s)
                but.setCheckable(True)
                but.setStyleSheet("QPushButton::checked { background: cyan }")
                but.setObjectName("strength")
                but.sh = sh
                but.site = site
                if s == picked:
                    but.setChecked(True)
                bg.addButton(but)
                lo.addWidget(but)
            lo.addStretch()
            
        w.layout().addWidget(QtGui.QLabel("Mark data (points) as:"))
        lvls = QtGui.QWidget()
        lvls.setLayout(QtGui.QHBoxLayout())
        w.layout().addWidget(lvls)
        lo = lvls.layout()
        w.bg = QtGui.QButtonGroup()
        
        picked = "don't mark"
        cur.execute("""select status 
                         from glrig2_misc.locale_mapped
                        where seg_hash = %s""", [sh])
        res = cur.fetchall()
        if res:
            picked = res[0][0]
        
        for s in 'assigned (done)', 'needs review', "don't mark":
            but = QtGui.QPushButton(s)
            but.setCheckable(True)
            but.setStyleSheet("QPushButton::checked { background: cyan }")
            but.sh = sh
            but.setObjectName('status')
            if s == picked:
                but.setChecked(True)
            w.bg.addButton(but)
            lo.addWidget(but)
        lo.addStretch()

        self.jump.setCurrentIndex(
		    self.jump.findText(str(int(sh))))  # avoid confusion
        
        sa = QtGui.QScrollArea()
        self.options.layout().addWidget(sa)
        sa.setWidget(w)
        w.show()
        self.options.show()

        self.sh_n += 1

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
        
        

