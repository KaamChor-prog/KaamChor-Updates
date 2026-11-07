"""KaamChor Pro desktop presentation. The automation engine is supplied unchanged."""
import asyncio
import csv
import os
import app_updates
import base64
import html
import queue
import sys
import threading
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Property, QPropertyAnimation, QEasingCurve, QRectF, QSettings, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient, QPainterPath
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QFrame, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QSpinBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QDialog, QGraphicsDropShadowEffect, QAbstractButton, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox)

PALETTES = {
    'light': dict(bg='#EEF2FA', ink='#18243A', muted='#64748B', accent='#007AFF',
        card=(255,255,255,192), edge=(255,255,255,235), field='rgba(255,255,255,175)',
        border='rgba(130,155,190,45)', soft='rgba(255,255,255,150)', glow='#CEDDFF',
        done='#087F5B', warn='#956500', error='#C42B43'),
    'dark': dict(bg='#0B1121', ink='#F2F5FF', muted='#9AAAC4', accent='#459AFF',
        card=(31,43,67,190), edge=(190,213,255,48), field='rgba(13,23,43,155)',
        border='rgba(177,200,242,42)', soft='rgba(102,136,191,35)', glow='#243C70',
        done='#7DE3BD', warn='#F4C879', error='#FFA6B7'),
}


THEME_NAMES = [('light','Light'),('dark','Dark'),('navy_gold','Navy Gold'),
               ('ocean','Ocean Blue'),('emerald','Emerald'),('purple','Purple')]
for key, accent, bg, glow in (
    ('navy_gold','#E6BD68','#10182A','#443922'),
    ('ocean','#51C7F5','#071E30','#123F60'),
    ('emerald','#54DBAD','#0B241E','#19513E'),
    ('purple','#C5A0FF','#20132F','#4B2B66')):
    PALETTES[key] = dict(PALETTES['dark'], accent=accent, bg=bg, glow=glow)


def pixmap(data):
    result = QPixmap()
    result.loadFromData(base64.b64decode(data))
    return result


class Ambient(QWidget):
    def __init__(self):
        super().__init__()
        self.mode = 'light'
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(PALETTES[self.mode]['bg']))
        colors = ['#B7D6FF', '#D9C8F7', '#BFEAE4'] if self.mode == 'light' else ['#183B72', '#352356', '#103F48']
        for x, y, radius, color in ((.05,.1,.65,colors[0]), (.93,.15,.55,colors[1]), (.65,.95,.6,colors[2])):
            r = max(self.width(), self.height())*radius
            grad = QRadialGradient(self.width()*x,self.height()*y,r)
            c = QColor(color)
            grad.setColorAt(0,c)
            c.setAlpha(0)
            grad.setColorAt(1,c)
            p.fillRect(self.rect(),grad)


class GlassCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode='light'
        self.tint=None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        shadow=QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0,9)
        shadow.setColor(QColor(13,32,70,25))
        self.setGraphicsEffect(shadow)
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        box=QRectF(self.rect()).adjusted(1,1,-1,-1)
        palette=PALETTES[self.mode]
        fill=QLinearGradient(box.topLeft(),box.bottomRight())
        c=QColor('#101D43') if self.objectName()=='sidebar' else QColor(self.tint) if self.tint and self.mode=='light' else QColor(*palette['card'])
        fill.setColorAt(0,c)
        c2=QColor(c);c2.setAlpha(255 if self.objectName()=='sidebar' else max(110,c.alpha()-35))
        fill.setColorAt(1,c2)
        p.setBrush(fill)
        p.setPen(QPen(QColor(*palette['edge']),1.2))
        p.drawRoundedRect(box,25,25)
        p.setPen(QPen(QColor(255,255,255,80 if self.mode=='light' else 22),1))
        p.drawLine(28,2,self.width()-28,2)


class HeroBanner(QWidget):
    def __init__(self,data):
        super().__init__();self.art=pixmap(data);self.setMinimumHeight(240);self.setMaximumHeight(280)
        self.setAccessibleName('KaamChor Pro. Smart work. More chill.')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path=QPainterPath();path.addRoundedRect(QRectF(self.rect()),18,18);p.setClipPath(path)
        p.fillRect(self.rect(),QColor('#152854'))
        # Fit the complete banner without cropping the logo or mascot.
        scaled=self.art.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((self.width()-scaled.width())//2,(self.height()-scaled.height())//2,scaled)


class ProgressRing(QWidget):
    def __init__(self):
        super().__init__();self.value=0;self.mode='light';self.setFixedSize(106,106)
    def setValue(self,value):self.value=max(0,min(100,value));self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring=QRectF(9,9,88,88);p.setPen(QPen(QColor('#D9DFF5' if self.mode=='light' else '#334366'),9));p.drawEllipse(ring)
        p.setPen(QPen(QColor('#6856DC'),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.drawArc(ring,90*16,-int(self.value*3.6*16))
        p.setPen(QColor(PALETTES[self.mode]['ink']));p.setFont(QFont('Segoe UI',21,QFont.Weight.Bold))
        p.drawText(QRectF(0,24,106,38),Qt.AlignmentFlag.AlignCenter,str(self.value)+'%')
        p.setFont(QFont('Segoe UI',9));p.drawText(QRectF(0,60,106,23),Qt.AlignmentFlag.AlignCenter,'Progress')


class ThemeSwitch(QAbstractButton):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(140,42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName('Dark appearance')
        self._offset=3.0
        self.animation=QPropertyAnimation(self,b'offset',self)
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self.slide)
    def get_offset(self):return self._offset
    def set_offset(self,value):self._offset=value;self.update()
    offset=Property(float,get_offset,set_offset)
    def slide(self,checked):
        self.animation.stop()
        self.animation.setStartValue(self._offset)
        self.animation.setEndValue(71.0 if checked else 3.0)
        self.animation.start()
        self.setToolTip('Switch to Light' if checked else 'Switch to Dark')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark=self.isChecked()
        p.setPen(QPen(QColor(255,255,255,55 if dark else 170),1))
        p.setBrush(QColor(24,37,62,140) if dark else QColor(235,241,251,180))
        p.drawRoundedRect(QRectF(0.5,0.5,139,41),21,21)
        grad=QLinearGradient(0,0,0,42)
        grad.setColorAt(0,QColor('#4979B7') if dark else QColor('white'))
        grad.setColorAt(1,QColor('#315687') if dark else QColor('#E7F0FF'))
        p.setBrush(grad);p.setPen(QPen(QColor(255,255,255,100),1))
        p.drawRoundedRect(QRectF(self._offset,3,66,36),18,18)
        for rect,text,selected in ((QRectF(3,3,66,36),'Light',not dark),(QRectF(71,3,66,36),'Dark',dark)):
            p.setPen(QColor('#FFFFFF') if dark and selected else QColor('#263958') if not dark else QColor('#B8C7DE'))
            p.drawText(rect,Qt.AlignmentFlag.AlignCenter,text)


class GlassApp:
    def __init__(self, backend, supplied_name=None):
        self.backend=backend
        self.settings=QSettings("AryanMalik","KaamChorPro")
        self.pause=threading.Event();self.records={};self.completed_count=0;self.total_count=0
        self.qt=QApplication.instance() or QApplication(sys.argv)
        families=set(QFontDatabase.families())
        self.font_family=next((f for f in ('SF Pro Display','SF Pro Text','Segoe UI Variable','Segoe UI','Inter','DejaVu Sans') if f in families),'Sans Serif')
        self.qt.setFont(QFont(self.font_family,10))
        from brand_art import AVATAR_PNG
        self.icon=QIcon(pixmap(AVATAR_PNG))
        self.qt.setWindowIcon(self.icon)
        self.mode='light'
        self.events=queue.Queue();self.stop=threading.Event();self.running=False;self.log_messages=[]
        self.cancelled=False;self.failed=False
        name=supplied_name if supplied_name is not None else (self.settings.value("name","") or self.ask_name())
        if name is None:
            self.cancelled=True;return
        self.user_name,self.greeting=backend.personalized_greeting(name)
        self.settings.setValue("name",self.user_name)
        owner=self
        class Window(QMainWindow):
            def closeEvent(self,event):
                if owner.running:
                    owner.request_stop();event.ignore()
                else:
                    if owner.installing_update:
                        owner.update_cancel.set()
                        owner.status.setText('Cancelling update…')
                        event.ignore();return
                    owner.save_preferences();event.accept()
        self.window=Window()
        self.window.setWindowTitle('KaamChor Pro v'+app_updates.APP_VERSION)
        self.window.resize(1440,940)
        self.window.setMinimumSize(1100,740)
        self.ambient=Ambient()
        self.window.setCentralWidget(self.ambient)
        outer=QHBoxLayout(self.ambient);outer.setContentsMargins(14,14,14,14);outer.setSpacing(14)
        self.cards=[]
        sidebar=self.card();sidebar.setObjectName("sidebar");sidebar.setFixedWidth(200)
        side=QVBoxLayout(sidebar);side.setContentsMargins(16,24,16,20);side.setSpacing(10)
        from brand_art import HERO_PNG, AVATAR_PNG
        avatar=QLabel();avatar.setPixmap(pixmap(AVATAR_PNG).scaled(88,88,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));avatar.setFixedHeight(94);avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(avatar)
        wordmark=QLabel('<b>KaamChor <span style="color:#F5BD47">Pro</span></b>');wordmark.setStyleSheet('font-size:20px;color:white;background:transparent;');wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter);side.addWidget(wordmark)
        strap=self.label('Smart work. More chill.',9,'muted');strap.setAlignment(Qt.AlignmentFlag.AlignCenter);side.addWidget(strap);side.addSpacing(20)
        self.nav_buttons={}
        for text in ('Dashboard','Students','Results','Settings'):
            button=QPushButton(text);button.setObjectName('nav');button.setCheckable(True);button.setAutoExclusive(True)
            button.clicked.connect(lambda checked=False,key=text:self.navigate(key))
            self.nav_buttons[text]=button;side.addWidget(button)
        self.nav_buttons['Dashboard'].setChecked(True)
        side.addStretch();help_button=QPushButton('Help & guide');help_button.setObjectName('nav');help_button.clicked.connect(self.show_help);side.addWidget(help_button)
        side.addWidget(self.label('v'+app_updates.APP_VERSION+'  ·  Windows',9,'muted'));outer.addWidget(sidebar)
        scroll=QScrollArea();scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget {background: transparent;}')
        content=QWidget();content.setObjectName('content');scroll.setWidget(content);outer.addWidget(scroll)
        layout=QVBoxLayout(content);layout.setContentsMargins(8,8,8,10);layout.setSpacing(12)
        self.scroll=scroll;self.content_layout=layout
        header=self.card();header_layout=QHBoxLayout(header);header_layout.setContentsMargins(18,10,18,10)
        titles=QVBoxLayout();titles.setSpacing(3)
        titles.addWidget(self.label('Welcome back, '+self.user_name,16))
        titles.addWidget(self.label('Your automation workspace',9,'muted'))
        header_layout.addLayout(titles,1)
        self.theme_picker=QComboBox();self.theme_picker.setToolTip('Choose your theme')
        for key,label in THEME_NAMES:self.theme_picker.addItem(label,key)
        self.theme_picker.currentIndexChanged.connect(lambda _:self.set_theme(self.theme_picker.currentData()))
        header_layout.addWidget(self.theme_picker)
        self.update_busy=False;self.installing_update=False;self.available_update=None
        self.update_cancel=threading.Event()
        self.update_button=QPushButton('Check for updates')
        self.update_button.clicked.connect(self.update_clicked)
        header_layout.addWidget(self.update_button)
        layout.addWidget(header)
        hero=HeroBanner(HERO_PNG);layout.addWidget(hero)
        welcome=QHBoxLayout();welcome.addWidget(self.label('Overview',13,'muted'),1)
        self.status=self.label('Ready to start',10,'badge');welcome.addWidget(self.status)
        layout.addLayout(welcome)
        workflow=self.label('1  Import students     →     2  Review settings     →     3  Run automation',11,'muted')
        stats=QHBoxLayout();self.stat_labels={}
        for key in ('Total','Completed','In Progress','Pending'):
            card=self.card();card.tint={'Total':'#DDEBFF','Completed':'#DAF1E8','In Progress':'#E8E1FF','Pending':'#FFF0D9'}[key];box=QVBoxLayout(card);box.setContentsMargins(18,12,18,12)
            metric_name={'Total':'◉   Total Students','Completed':'✓   Completed','In Progress':'↻   In Progress','Pending':'◷   Pending'}[key]
            box.addWidget(self.label(metric_name,10,'muted'));value=self.label('0',24)
            self.stat_labels[key]=value;box.addWidget(value);stats.addWidget(card)
        layout.addLayout(stats)
        setup=self.card();form=QVBoxLayout(setup);form.setContentsMargins(20,18,20,18);form.setSpacing(10)
        row=QHBoxLayout();row.addWidget(self.label('Start your automation',16),1);row.addWidget(self.label('EXCEL / CSV',10,'muted'));form.addLayout(row);form.addWidget(workflow)
        file_row=QHBoxLayout();file_row.setSpacing(10)
        self.path=QLineEdit();self.path.setPlaceholderText('Choose your student spreadsheet…');self.path.setMinimumHeight(46)
        file_row.addWidget(self.path,1)
        self.browse=QPushButton('Browse file');self.browse.setObjectName('secondary');self.browse.clicked.connect(self.choose);file_row.addWidget(self.browse)
        form.addLayout(file_row)
        self.file_hint=self.label('One row for each account, password and template link.',10,'muted');form.addWidget(self.file_hint)
        divider=QFrame();divider.setObjectName('divider');divider.setFixedHeight(1);form.addWidget(divider)
        settings=QHBoxLayout();settings.setSpacing(22)
        self.parallel=QSpinBox();self.parallel.setRange(1,40);self.parallel.setValue(3)
        self.timeout=QSpinBox();self.timeout.setRange(60,3600);self.timeout.setValue(600);self.timeout.setSingleStep(60)
        for label,control,helptext in (('Parallel accounts',self.parallel,'Accounts running at the same time'),('Login / editor wait',self.timeout,'Seconds allowed for each sign-in')):
            col=QVBoxLayout();col.setSpacing(6);col.addWidget(self.label(label,11));control.setMinimumHeight(44);col.addWidget(control);col.addWidget(self.label(helptext,9,'muted'));settings.addLayout(col,1)
        form.addLayout(settings);layout.addWidget(setup)
        controls=QHBoxLayout();controls.setSpacing(12)
        self.start_button=QPushButton('Start automation');self.start_button.setObjectName('primary');self.start_button.setMinimumWidth(150);self.start_button.clicked.connect(self.start)
        self.stop_button=QPushButton('Stop');self.stop_button.setObjectName('stop');self.stop_button.setEnabled(False);self.stop_button.clicked.connect(self.request_stop)
        controls.addWidget(self.start_button);controls.addWidget(self.stop_button)
        self.pause_button=QPushButton('Pause');self.pause_button.setEnabled(False);self.pause_button.clicked.connect(self.toggle_pause);controls.addWidget(self.pause_button)
        self.retry_button=QPushButton('Retry failed');self.retry_button.clicked.connect(lambda:self.start(True));controls.addWidget(self.retry_button)
        controls.addStretch()
        self.run_hint=self.label('Your workspace is ready.',10,'muted');form.addWidget(self.run_hint)
        form.addLayout(controls)
        self.bar=QProgressBar();self.bar.setRange(0,max(1,self.total_count));self.bar.setValue(self.completed_count);self.bar.setTextVisible(False);self.bar.setFixedHeight(8);form.addWidget(self.bar)
        results_card=self.card();results_box=QVBoxLayout(results_card);results_box.setContentsMargins(20,16,20,16)
        tools=QHBoxLayout();tools.addWidget(self.label('Student results',16))
        self.search=QLineEdit();self.search.setPlaceholderText('Search name or email');self.search.textChanged.connect(self.refresh_results);tools.addWidget(self.search,1)
        self.filter=QComboBox();self.filter.addItems(['All','Done','Failed','Review','Pending','Running','Stopped','Skipped']);self.filter.currentTextChanged.connect(self.refresh_results);tools.addWidget(self.filter)
        results_box.addLayout(tools)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Student Name','Adobe Email','Status','Published Link','Details'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setMinimumHeight(180);self.table.setAlternatingRowColors(True);self.table.verticalHeader().setDefaultSectionSize(36);results_box.addWidget(self.table)
        copies=QHBoxLayout()
        for title,action in [('Copy Link',lambda:self.copy_results('link')),('Copy Details',lambda:self.copy_results('one')),('Copy Selected',lambda:self.copy_results('selected')),('Copy All',lambda:self.copy_results('all')),('Export Results',self.export_results),('Open Output',self.open_output)]:
            button=QPushButton(title);button.setProperty("compact",True);button.clicked.connect(action);copies.addWidget(button)
        results_box.addLayout(copies);layout.addWidget(results_card)
        activity=self.card();log_layout=QVBoxLayout(activity);log_layout.setContentsMargins(22,18,22,18);log_layout.setSpacing(12)
        log_title=QHBoxLayout();log_title.addWidget(self.label('Live activity',14),1);report=QPushButton('Save report');report.setProperty('compact',True);report.clicked.connect(self.save_report);log_title.addWidget(report);log_layout.addLayout(log_title)
        self.logbox=QTextEdit();self.logbox.setReadOnly(True);self.logbox.setMinimumHeight(130);self.logbox.setObjectName('activity');self.logbox.document().setMaximumBlockCount(3000);progress_row=QHBoxLayout();self.ring=ProgressRing();progress_row.addWidget(self.ring)
        stage_text=QVBoxLayout();stage_text.addWidget(self.label('Live progress',12));self.current_stage=self.label('Ready to start',10,'muted');stage_text.addWidget(self.current_stage);progress_row.addLayout(stage_text,1);log_layout.addLayout(progress_row)
        log_layout.addWidget(self.logbox,1)
        layout.removeWidget(setup)
        mid=QHBoxLayout();mid.setSpacing(14)
        mid.addWidget(setup,3);mid.addWidget(activity,2)
        layout.insertLayout(layout.indexOf(results_card),mid)
        self.sections={'Dashboard':header,'Students':setup,'Results':results_card,'Settings':setup}
        layout.setStretch(layout.indexOf(results_card),1)
        footer=self.label('KaamChor Pro '+app_updates.APP_VERSION+'   ·   Original Excel preserved',9,'muted');footer.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(footer)
        self.path.setText(self.settings.value('source',''))
        self.parallel.setValue(int(self.settings.value('parallel',3)))
        self.timeout.setValue(int(self.settings.value('timeout',600)))
        saved_mode=self.settings.value('theme','light')
        if saved_mode not in PALETTES:saved_mode='light'
        self.theme_picker.setCurrentIndex(self.theme_picker.findData(saved_mode));self.set_theme(saved_mode)
        if self.path.text():
            try:self.load_results()
            except Exception:pass
        self.timer=QTimer();self.timer.timeout.connect(self.poll);self.timer.start(150)
        if app_updates.UPDATE_FEED_URL:QTimer.singleShot(2000,lambda:self.check_updates(False))

    def navigate(self,key):
        self.scroll.ensureWidgetVisible(self.sections[key],0,12)
        if key=='Students':self.path.setFocus()
        elif key=='Results':self.search.setFocus()
        elif key=='Settings':self.parallel.setFocus()

    def update_clicked(self):
        if self.installing_update:
            self.update_cancel.set();self.update_button.setEnabled(False)
            self.update_button.setText('Cancelling…');return
        if self.update_busy:return
        if self.available_update:self.offer_update()
        else:self.check_updates(True)

    def check_updates(self,manual=True):
        if self.update_busy:return
        self.update_busy=True;self.update_button.setEnabled(False)
        self.update_button.setText('Checking…')
        def worker():
            try:self.events.put(('update_checked',(app_updates.check_update(),manual,None)))
            except Exception as exc:self.events.put(('update_checked',(None,manual,str(exc))))
        threading.Thread(target=worker,daemon=True).start()

    def offer_update(self):
        if self.running:
            QMessageBox.information(self.window,'Update available','Finish or stop automation before installing the update.');return
        release=self.available_update
        if not release:return
        if sys.platform!='win32' or not getattr(sys,'frozen',False):
            QMessageBox.information(self.window,'Windows EXE required','Update installation is available in the Windows EXE build.');return
        answer=QMessageBox.question(self.window,'Update available',
            'Version '+release['version']+' is available.\n\n'+release.get('notes','')[:3000]+
            '\n\nDownload, install and restart now?')
        if answer!=QMessageBox.StandardButton.Yes:return
        self.update_cancel.clear()
        self.update_busy=True;self.installing_update=True
        self.set_running(True);self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.update_button.setEnabled(True);self.update_button.setText('Cancel update')
        self.status.setText('Connecting to GitHub…')
        def worker():
            try:
                path=app_updates.download_update(release,
                    progress=lambda done,total:self.events.put(('update_progress',(done,total))),
                    cancel=self.update_cancel,
                    status=lambda message:self.events.put(('update_status',message)))
                self.events.put(('update_downloaded',(path,None)))
            except app_updates.DownloadCancelled:self.events.put(('update_downloaded',(None,'cancelled')))
            except Exception as exc:self.events.put(('update_downloaded',(None,str(exc))))
        threading.Thread(target=worker,daemon=True).start()

    def label(self,text,size=10,role='text'):
        result=QLabel(text);result.setProperty('role',role)
        font=QFont(self.font_family,size)
        if size>=14 or role=='badge':font.setWeight(QFont.Weight.DemiBold)
        result.setFont(font)
        result.setWordWrap(True)
        return result

    def card(self):
        result=GlassCard();self.cards.append(result);return result

    def ask_name(self):
        dialog=QDialog();dialog.setWindowTitle('Welcome to KaamChor Pro');dialog.setMinimumWidth(460)
        dialog.setStyleSheet('QDialog {background:#F1F5FF;} QLabel {color:#18243A;} QLineEdit {background:white;border:1px solid #DAE3F3;border-radius:16px;padding:14px;} QPushButton {background:#007AFF;color:white;border:0;border-radius:21px;padding:14px;}')
        body=QVBoxLayout(dialog);body.setContentsMargins(30,28,30,28);body.setSpacing(14)
        logo=QLabel();logo.setAlignment(Qt.AlignmentFlag.AlignCenter);logo.setPixmap(self.icon.pixmap(96,96));body.addWidget(logo)
        body.addWidget(self.label('What should we call you?',22))
        body.addWidget(self.label('A little introduction before we do the work.',10,'muted'))
        field=QLineEdit();field.setPlaceholderText('Your name');field.setMaxLength(50);body.addWidget(field)
        error=QLabel('');error.setStyleSheet('color:#C42B43');body.addWidget(error)
        submit=QPushButton('Let’s get to work');body.addWidget(submit)
        result={'name':None}
        def accept():
            try:result['name'],_=self.backend.personalized_greeting(field.text())
            except ValueError as exc:error.setText(str(exc));return
            dialog.accept()
        submit.clicked.connect(accept);field.returnPressed.connect(accept)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return None
        return result['name']

    def set_theme(self,mode):
        if mode not in PALETTES:mode='light'
        self.mode=mode;p=PALETTES[mode];dark=mode!='light'
        self.settings.setValue('theme',mode)
        self.ambient.mode=mode;self.ambient.update()
        if hasattr(self,'ring'):self.ring.mode=mode;self.ring.update()
        for card in self.cards:card.mode=mode;card.update()
        self.window.setStyleSheet(f'''
            QWidget {{color:{p['ink']};}}
            QWidget#content, QLabel {{background:transparent;}}
            QMessageBox {{background:{p['bg']};}}
            QMessageBox QLabel {{color:{p['ink']};}}
            QTableWidget, QComboBox {{background:{p['field']};color:{p['ink']};border:1px solid {p['border']};border-radius:10px;selection-background-color:{p['accent']};alternate-background-color:{p['soft']};gridline-color:{p['border']};}}
            QHeaderView::section {{background:{p['bg']};color:{p['muted']};padding:9px;border:0;}}
            QLabel[role="muted"] {{color:{p['muted']};}}
            QLabel[role="badge"] {{background:{p['soft']};color:{p['accent']};border:1px solid {p['border']};border-radius:15px;padding:8px 14px;}}
            QLineEdit, QSpinBox {{background:{p['field']};border:1px solid {p['border']};border-radius:16px;padding:7px 14px;selection-background-color:{p['accent']};}}
            QLineEdit:focus, QSpinBox:focus {{border:1px solid {p['accent']};}}
            QSpinBox::up-button {{width:25px;border:0;subcontrol-origin:border;subcontrol-position:top right;}}
            QSpinBox::down-button {{width:25px;border:0;subcontrol-origin:border;subcontrol-position:bottom right;}}
            QPushButton {{background:{p['soft']};border:1px solid {p['border']};border-radius:11px;padding:10px 14px;font-weight:600;}}
            QPushButton:hover {{border:1px solid {p['accent']};background:{p['field']};}}
            QPushButton:pressed {{padding-top:15px;padding-bottom:11px;}}
            QPushButton#primary {{border-radius:20px;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {p['accent']},stop:1 {p['glow']});color:white;border:1px solid rgba(255,255,255,145);}}
            QPushButton#primary:hover {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {p['accent']},stop:1 {p['glow']});}}
            QPushButton#stop {{border-radius:20px;color:{'#FFA6B7' if dark else '#B93850'};}}
            QPushButton[compact="true"] {{padding:8px 12px;border-radius:12px;}}
            QFrame#sidebar {{background:{p['bg'] if dark else "#101D43"};border-radius:22px;}}
            QFrame#sidebar QLabel {{color:#C4CFE8;}}
            QPushButton#nav {{background:transparent;color:#DDE6FB;text-align:left;border-radius:12px;padding:12px 16px;border:0;}}
            QPushButton#nav:checked {{background:#424AAB;color:white;}}
            QLabel#monogram {{background:{p['accent']};color:white;border-radius:15px;}}
            QPushButton:disabled {{color:{p['muted']};background:{p['soft']};border:1px solid {p['border']};}}
            QFrame#divider {{background:{p['border']};border:0;}}
            QTextEdit#activity {{background:transparent;border:0;selection-background-color:{p['accent']};font-family:"{self.font_family}";font-size:12px;}}
            QProgressBar {{background:{p['border']};border:0;border-radius:2px;}}
            QProgressBar::chunk {{background:{p['accent']};border-radius:2px;}}
            QScrollBar:vertical {{background:transparent;width:8px;margin:1px;}}
            QScrollBar::handle:vertical {{background:{p['border']};border-radius:4px;min-height:30px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:transparent;}}
        ''')

        if self.log_messages:
            self.logbox.setHtml('<br>'.join(self.format_log(line) for line in self.log_messages))

    def save_preferences(self):
        for key,value in [('source',self.path.text()),('parallel',self.parallel.value()),('timeout',self.timeout.value()),('theme',self.mode)]:self.settings.setValue(key,value)

    def toggle_pause(self):
        if self.pause.is_set():
            self.pause.clear();self.pause_button.setText('Pause');self.status.setText('Running')
        else:
            self.pause.set();self.pause_button.setText('Resume');self.status.setText('Pausing queue')
            self.run_hint.setText('Active students finish; new accounts wait.')

    def load_results(self):
        headers,values,rows=self.backend.read_rows(self.path.text())
        previous=self.backend.Results(self.path.text(),headers,values)
        self.records={item['row']:dict(name=item.get('name',''),email=item['email'],status='Pending',stage='',link='',**{}) for item in rows}
        for item in rows:
            old=previous.previous(item)
            if old:self.records[item['row']].update(old)
        self.refresh_results()

    def refresh_results(self,*args):
        if not hasattr(self,'table'):return
        query=self.search.text().casefold();status=self.filter.currentText()
        self.visible_rows=[r for _,r in sorted(self.records.items()) if query in (r.get('name','')+' '+r['email']).casefold() and (status=='All' or r['status']==status)]
        self.table.setRowCount(len(self.visible_rows))
        for row,rec in enumerate(self.visible_rows):
            for col,key in enumerate(('name','email','status','link','stage')):
                cell=QTableWidgetItem(str(rec.get(key,'')))
                if key=='status':cell.setForeground(QColor(PALETTES[self.mode]['done'] if rec['status']=='Done' else PALETTES[self.mode]['error'] if rec['status'] in ('Failed','Review','Stopped') else PALETTES[self.mode]['accent']))
                self.table.setItem(row,col,cell)
        counts={'Total':len(self.records),'Completed':sum(r['status']=='Done' for r in self.records.values()),'In Progress':sum(r['status']=='Running' for r in self.records.values()),'Pending':sum(r['status']=='Pending' for r in self.records.values())}
        for key,value in counts.items():self.stat_labels[key].setText(str(value))

    def copy_results(self,mode):
        selected=sorted({i.row() for i in self.table.selectionModel().selectedRows()})
        rows=self.visible_rows if mode=='all' else [self.visible_rows[i] for i in selected]
        if mode in ('link','one'):rows=rows[:1]
        rows=[r for r in rows if r.get('link') and r['status']=='Done']
        if not rows:QMessageBox.information(self.window,'Copy results','Select a completed student with a published link.');return
        text='\n\n'.join(r['link'] if mode=='link' else 'Name: '+r.get('name','')+'\nAdobe Email: '+r['email']+'\nPublished Link: '+r['link'] for r in rows)
        self.qt.clipboard().setText(text);self.run_hint.setText(str(len(rows))+' result(s) copied')

    def export_results(self):
        path,_=QFileDialog.getSaveFileName(self.window,'Export results','KaamChor_Results.xlsx','Excel (*.xlsx);;CSV (*.csv)')
        if not path:return
        values=[['Student Name','Adobe Email','Status','Published Link','Details']]+[[r.get(k,'') for k in ('name','email','status','link','stage')] for _,r in sorted(self.records.items())]
        # Export values as literal strings, including names beginning with formula characters.
        try:
            if path.lower().endswith('.xlsx'):
                from openpyxl import Workbook
                wb=Workbook();ws=wb.active;ws.title='Results'
                for row in values:
                    ws.append(row)
                    for cell in ws[ws.max_row]:cell.data_type='s'
                ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
                for col,width in zip('ABCDE',(26,40,18,65,35)):ws.column_dimensions[col].width=width
                wb.save(path);wb.close()
            else:
                with open(path,'w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows([["'"+v if str(v).startswith(('=','+','-','@')) else v for v in row] for row in values])
            self.run_hint.setText('Results exported')
        except Exception as exc:QMessageBox.warning(self.window,'Export failed',str(exc))

    def open_output(self):
        if not self.path.text():return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.path.text()).resolve().parent)))

    def save_report(self):
        path,_=QFileDialog.getSaveFileName(self.window,'Save error report','KaamChor_Report.txt','Text (*.txt)')
        if path:
            try:Path(path).write_text('KaamChor Pro '+app_updates.APP_VERSION+'\n'+'\n'.join(self.log_messages),encoding='utf-8');self.run_hint.setText('Report saved')
            except OSError as exc:QMessageBox.warning(self.window,'Save report',str(exc))

    def show_help(self):
        QMessageBox.information(self.window,'KaamChor Pro Help','1. Choose Excel/CSV with Adobe Email, Password and Template Link. Student Name is optional.\n2. Start automation. Original spreadsheet stays unchanged.\n3. Select completed results to copy links or details.\n\nPause stops new accounts; active accounts finish. Retry failed retries Failed/Stopped rows only. Review rows need manual publication checks to avoid duplicate publishing. Reopen the same source to resume saved progress.\n\nUpdates are available from Check for updates.')

    def choose(self):
        path,_=QFileDialog.getOpenFileName(self.window,'Choose student spreadsheet','','Excel / CSV (*.xlsx *.csv)')
        if path:
            self.path.setText(path);self.file_hint.setText(Path(path).name+' selected')
            try:self.load_results();self.save_preferences()
            except Exception as exc:QMessageBox.warning(self.window,'Check input',str(exc))

    def start(self,retry_failed=False):
        if self.running or self.installing_update:return
        try:
            path=str(Path(self.path.text()).resolve())
            _,_,rows=self.backend.read_rows(path)
            parallel,timeout=self.parallel.value(),self.timeout.value()
        except Exception as exc:QMessageBox.warning(self.window,'Check input',str(exc));return
        self.load_results();self.save_preferences()
        self.pause.clear();self.completed_count=0;self.total_count=len(rows);self.ring.setValue(0)
        self.stop.clear();self.running=True;self.failed=False
        self.file_hint.setText(f'{len(rows)} accounts loaded')
        self.status.setText('Running');self.run_hint.setText(f'{len(rows)} accounts in this batch')
        self.set_running(True);self.bar.setRange(0,self.total_count);self.bar.setValue(0)
        def worker():
            try:asyncio.run(self.backend.Engine(self.stop,self.events,parallel,timeout,self.pause,retry_failed).run(path))
            except Exception as exc:
                self.events.put(('failure',type(exc).__name__))
            finally:self.events.put(('finished',None))
        threading.Thread(target=worker,daemon=True).start()

    def set_running(self,running):
        for control in (self.start_button,self.browse,self.path,self.parallel,self.timeout):control.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.pause_button.setEnabled(running);self.retry_button.setEnabled(not running)
        self.pause_button.setText("Pause")

    def request_stop(self):
        if self.running:
            self.pause.clear();self.stop.set();self.status.setText('Stopping');self.run_hint.setText('Closing active sessions…');self.stop_button.setEnabled(False)

    def format_log(self,text):
        p=PALETTES[self.mode]
        color=p['error'] if 'Failed' in text or 'failed' in text else p['warn'] if 'Skipped' in text or 'Review' in text else p['done'] if 'Done' in text else p['ink']
        return f'<span style="color:{color}">{html.escape(text)}</span>'

    def append_log(self,text):
        if hasattr(self,'current_stage'):self.current_stage.setText(text[:150])
        self.log_messages.append(text)
        if len(self.log_messages)>3000:self.log_messages=self.log_messages[-3000:]
        self.logbox.append(self.format_log(text))
        bar=self.logbox.verticalScrollBar();bar.setValue(bar.maximum())

    def poll(self):
        while not self.events.empty():
            kind,value=self.events.get_nowait()
            if kind=='record':
                row,record=value;self.records[row]=record;self.refresh_results()
            elif kind=='progress':
                self.completed_count+=value;self.bar.setValue(self.completed_count);self.ring.setValue(round(100*self.completed_count/max(1,self.total_count)))
            elif kind=='update_checked':
                release,manual,error=value
                self.update_busy=False;self.update_button.setEnabled(True)
                self.available_update=release
                self.update_button.setText('Update available · '+release['version'] if release else 'Check for updates')
                if error:
                    if manual:QMessageBox.information(self.window,'Updates',error)
                elif release:
                    if manual:self.offer_update()
                elif manual:QMessageBox.information(self.window,'Updates','You are using the latest version.')
            elif kind=='update_progress':
                done,total=value
                self.update_button.setText(f'Cancel update · {100*done/max(1,total):.0f}%')
                self.status.setText(f'Update: {done/1048576:.1f} / {total/1048576:.1f} MB')
            elif kind=='update_status':
                self.status.setText(value)
            elif kind=='update_downloaded':
                path,error=value
                if not error and self.update_cancel.is_set():
                    Path(path).unlink(missing_ok=True);Path(path).parent.rmdir();error='cancelled'
                if not error:
                    try:
                        self.status.setText('Installing update and restarting…')
                        app_updates.install_update(path)
                        self.qt.quit()
                        continue
                    except Exception as exc:error=str(exc)
                self.update_busy=False;self.installing_update=False
                self.set_running(False);self.update_button.setEnabled(True)
                self.update_button.setText('Update available')
                self.status.setText('Update cancelled' if error=='cancelled' else 'Update failed · Retry available')
                if error!='cancelled':QMessageBox.warning(self.window,'Update failed',error)
            elif kind=='log':self.append_log(value)
            elif kind=='failure':
                self.failed=True;self.append_log('Run failed: '+value+'. Check Chrome, input and output file lock.')
            elif kind=='finished':
                self.running=False;self.set_running(False);self.bar.setRange(0,max(1,self.total_count));self.bar.setValue(self.completed_count)
                self.status.setText('Stopped' if self.stop.is_set() else 'Needs attention' if self.failed else 'Batch finished')
                self.run_hint.setText('Check the output Status column.')

    def run(self):
        if self.cancelled:return
        self.window.show()
        self.qt.exec()
