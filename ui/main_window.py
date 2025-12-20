"""
WeLearn 自动学习工具 - 主窗口
多用户管理中心
"""
import os
import sys
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QMenuBar, QMenu, QAction,
    QMessageBox, QStatusBar, QSystemTrayIcon, QApplication, QStyle
)
from PyQt5.QtGui import QIcon, QBitmap, QPixmap, QPainter, QBrush

try:
    from ui.account_view import AccountView
    from ui.account_detail import AccountDetailDialog
    from core.account_manager import Account
except ImportError:
    try:
        from .account_view import AccountView
        from .account_detail import AccountDetailDialog
        from ..core.account_manager import Account
    except ImportError:
        try:
            import account_view as AccountView_module
            import account_detail as AccountDetailDialog_module
            import account_manager as Account_manager_module
            
            AccountView = AccountView_module.AccountView
            AccountDetailDialog = AccountDetailDialog_module.AccountDetailDialog
            Account = Account_manager_module.Account
        except ImportError:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, current_dir)
            sys.path.insert(0, os.path.dirname(current_dir))
            
            from account_view import AccountView
            from account_detail import AccountDetailDialog
            from core.account_manager import Account


class WeLearnUI(QMainWindow):
    """
    主窗口
    现在作为多用户管理中心
    """
    
    def __init__(self):
        super().__init__()
        self.detail_dialogs = {}  # 存储打开的详情对话框
        self.tray_icon = None     # 系统托盘图标
        self.version = "V3.1"     # 软件版本号
        self.init_ui()
        self.init_tray()  # 初始化系统托盘
        
        self.show_startup_warning()  # 显示启动警告
        self.show_update_announcement()  # 显示更新公告
    
    def center_window(self):
        """将窗口居中显示在屏幕中央"""
        screen = QApplication.desktop().screenGeometry()
        window_frame = self.frameGeometry()
        x = (screen.width() - window_frame.width()) // 2
        y = (screen.height() - window_frame.height()) // 2
        self.move(x, y)
    
    def show(self):
        """重写show方法，在显示窗口后居中"""
        super().show()
        QTimer.singleShot(100, self.center_window)
    
    def init_ui(self):
        self.setWindowTitle("ZR | WeLearn学习助手 V3.1    致力于把大学生的时间还给大学生")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(800, 500)
        
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                app_path = sys._MEIPASS
            else:
                app_path = os.path.dirname(sys.executable)
        else:
            app_path = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.dirname(app_path)
        
        icon_path = os.path.join(app_path, 'ZR.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            print(f"已设置窗口图标: {icon_path}")
        else:
            print(f"图标文件不存在: {icon_path}")
        
        bg_path = os.path.join(app_path, 'ZR.png')
        if os.path.exists(bg_path):
            palette = self.palette()
            pixmap = QPixmap(bg_path)
            palette.setBrush(self.backgroundRole(), QBrush(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)))
            self.setPalette(palette)
            print(f"已设置背景图片: {bg_path}")
        else:
            print(f"背景图片文件不存在: {bg_path}")
        
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: rgba(255, 255, 255, 0.8);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.8);
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QHeaderView::section {
                background-color: rgba(240, 240, 240, 0.8);
                padding: 8px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        
        self.account_view = AccountView()
        self.account_view.open_detail_requested.connect(self.open_account_detail)
        self.setCentralWidget(self.account_view)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 添加账号开始使用")
        
        from PyQt5.QtWidgets import QLabel
        disclaimer_label = QLabel("本软件仅供学术交流，禁止用于商业途径")
        disclaimer_label.setStyleSheet("color: red; font-size: 14px; font-weight: bold; padding: 2px;")
        self.status_bar.addPermanentWidget(disclaimer_label)
    
    def create_menu_bar(self):
        """创建菜单栏"""
        pass
    
    def open_account_detail(self, account: Account):
        """打开账号详情对话框"""
        username = account.username
        
        if username in self.detail_dialogs:
            dialog = self.detail_dialogs[username]
            if dialog.isVisible():
                dialog.raise_()
                dialog.activateWindow()
                return
            else:
                del self.detail_dialogs[username]
        
        dialog = AccountDetailDialog(account, self)
        dialog.status_updated.connect(self.on_account_status_updated)
        dialog.finished.connect(lambda result, u=username: self.on_detail_closed(u))
        
        self.detail_dialogs[username] = dialog
        dialog.show()
        self.status_bar.showMessage(f"已打开账号详情: {username}")
    
    def on_account_status_updated(self, username: str, status: str, progress: str):
        """账号状态更新回调"""
        self.account_view.update_account_status(username, status, progress)
    
    def on_detail_closed(self, username: str):
        """详情对话框关闭回调"""
        if username in self.detail_dialogs:
            del self.detail_dialogs[username]
        self.account_view.refresh_table()
    
    def show_about(self):
        """显示关于对话框"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("关于 WeLearn 自动学习工具")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText(
            """
            <h3>WeLearn 自动学习工具</h3>
            <p>版本: 2.1 (ZR修改版)</p>
            <p>软件仅供学习参考使用，禁止用于一切商业用途</p>
            <p>禁止使用软件进行任何代刷牟利，以此造成的任何问题本人不负责任</p>
            """
        )
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        msg_box.show()
        msg_box.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                msg_box.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        msg_box.exec_()
    
    def open_github(self):
        """打开 GitHub 项目页面"""
        import webbrowser
        webbrowser.open("https://github.com/jhl337/Auto_WeLearn/")
    
    def show_startup_warning(self):
        """显示启动警告"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("使用声明")
        msg_box.setIcon(QMessageBox.Warning)
        
        warning_text = """版权声明：

本软件为WeLearn学习助手V3.1版本，由ZR修改并打包。

使用条款：
1. 本软件仅供学习交流使用，严禁用于任何商业用途
2. 软件版权归原开发者所有，本修改版仅作功能优化
3. 用户使用本软件所产生的任何后果由用户自行承担
4. 分发本软件时请保持版权信息完整

感谢您的理解与支持！"""
        msg_box.setText(warning_text)
        
        ok_button = msg_box.addButton("我已了解", QMessageBox.AcceptRole)
        msg_box.setDefaultButton(ok_button)
        
        msg_box.show()
        msg_box.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                msg_box.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        msg_box.exec_()
    
    def show_update_announcement(self):
        """显示更新公告"""
        # 检查是否已经选择不再提醒
        from PyQt5.QtCore import QSettings
        import os
        
        app_data_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ZR", "WeLearn学习助手")
        os.makedirs(app_data_path, exist_ok=True)
        settings_file = os.path.join(app_data_path, "settings.ini")
        
        settings = QSettings(settings_file, QSettings.IniFormat)
        dont_show = settings.value("General/dont_show_update_announcement", False, type=bool)
        
        print(f"更新公告设置: 不再提醒={dont_show}")
        print(f"设置文件路径: {settings_file}")
        
        if dont_show:
            print("用户已选择不再显示更新公告")
            return
            
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("更新公告")
        msg_box.setIcon(QMessageBox.Information)
        
        announcement_text = f"WeLearn学习助手 {self.version}\n\n"
        announcement_text += "添加账号保存功能\n\n"
        announcement_text += "V1.1\n"
        announcement_text += "-添加单元时长单位自选\n"
        announcement_text += "-修复关闭程序导致后台运行\n"
        announcement_text += "-添加后台运行彻底关闭自选\n"
        announcement_text += "-默认单元时长与并行数调整为合适数值\n\n"
        announcement_text += "V2.1\n"
        announcement_text += "-添加了Excel批量导入账号功能\n"
        announcement_text += "-输入框设置为半透明，以显示背景图片\n"
        announcement_text += "-修复了软件图标显示问题\n\n"
        announcement_text += "V3.1\n"
        announcement_text += "-修改了 `main_window.py` 中的导入语句，添加了多种导入方式的尝试\n"
        announcement_text += "-在打包配置文件中添加了隐藏导入模块列表\n"
        announcement_text += "-修复了 `account_view.py` 中的语法错误（中文引号问题）\n"
        announcement_text += "-修改了 `ui/workers.py` 中的 `calculate_unit_time` 方法\n"
        announcement_text += "-修复前：每个小节都获得完整的用户输入时长（例如每个小节都获得3小时）\n"
        announcement_text += "-修复后：输入的单元时长平均分配给每个小节（例如3小时/6个小节=每个小节30分钟）\n"
        announcement_text += "-确保每个单元的总时长就是用户输入的时长，平均分配给每个小节"
        
        msg_box.setText(announcement_text)
        
        ok_button = msg_box.addButton("确定", QMessageBox.AcceptRole)
        msg_box.setDefaultButton(ok_button)
        
        from PyQt5.QtWidgets import QCheckBox
        checkbox = QCheckBox("不再提醒")
        msg_box.setCheckBox(checkbox)
        
        msg_box.show()
        msg_box.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                msg_box.size(),
                QApplication.desktop().availableGeometry()
            )
        )
        
        msg_box.exec_()
        
        if checkbox.isChecked():
            print("用户选择不再显示更新公告")
            settings.setValue("General/dont_show_update_announcement", True)
            settings.sync()
            print("设置已保存")
        else:
            print("用户未勾选不再提醒")
    
    def closeEvent(self, event):
        """关闭窗口时的处理"""
        msg_box = QMessageBox(QMessageBox.Question, "关闭程序", "您希望如何关闭程序？")
        background_btn = msg_box.addButton("后台运行", QMessageBox.YesRole)
        close_btn = msg_box.addButton("完全关闭", QMessageBox.NoRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)
        msg_box.setDefaultButton(close_btn)
        
        # 获取主窗口的位置和大小
        main_window_geometry = self.frameGeometry()
        main_window_center = main_window_geometry.center()
        
        # 计算消息框的位置，使其在主窗口中央
        msg_box_size = msg_box.sizeHint()
        x = main_window_center.x() - msg_box_size.width() // 2
        y = main_window_center.y() - msg_box_size.height() // 2
        
        msg_box.move(x, y)
        
        reply = msg_box.exec_()
        
        if msg_box.clickedButton() == cancel_btn:
            event.ignore()
            return
        elif msg_box.clickedButton() == background_btn:
            self.hide()
            if self.tray_icon:
                self.tray_icon.showMessage(
                    "WeLearn 自动学习工具",
                    "程序已最小化到系统托盘，右键托盘图标可选择退出程序",
                    QSystemTrayIcon.Information,
                    3000
                )
            event.ignore()
            return
        else:
            for dialog in list(self.detail_dialogs.values()):
                dialog.close()
            self.detail_dialogs.clear()
            
            if self.tray_icon:
                self.tray_icon.hide()
            
            QApplication.quit()
            event.accept()
    
    def init_tray(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("系统不支持托盘功能")
            return
        
        self.tray_icon = self.create_tray_icon()
        
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self.show_from_tray)
        
        tray_menu.addSeparator()
        
        quit_action = tray_menu.addAction("退出程序")
        quit_action.triggered.connect(self.quit_from_tray)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        self.tray_icon.show()
    
    def create_tray_icon(self):
        """创建托盘图标"""
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                app_path = sys._MEIPASS
            else:
                app_path = os.path.dirname(sys.executable)
                if not os.path.exists(os.path.join(app_path, 'ZR.ico')):
                    internal_path = os.path.join(app_path, '_internal')
                    if os.path.exists(os.path.join(internal_path, 'ZR.ico')):
                        app_path = internal_path
        else:
            app_path = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.dirname(app_path)
        
        icon_path = os.path.join(app_path, 'ZR.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            print(f"已设置托盘图标: {icon_path}")
        else:
            print(f"托盘图标文件不存在: {icon_path}")
            icon = self.style().standardIcon(self.style().SP_ComputerIcon)
        
        return QSystemTrayIcon(icon, self)
    
    def show_from_tray(self):
        """从托盘恢复显示主窗口"""
        self.show()
        self.raise_()
        self.activateWindow()
    
    def quit_from_tray(self):
        """从托盘完全退出程序"""
        for dialog in list(self.detail_dialogs.values()):
            dialog.close()
        self.detail_dialogs.clear()
        
        if self.tray_icon:
            self.tray_icon.hide()
        
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()
    
    def on_tray_icon_activated(self, reason):
        """托盘图标激活事件"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_from_tray()
    
    def resizeEvent(self, event):
        """窗口大小改变时重新设置背景图片"""
        super().resizeEvent(event)
        
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                app_path = sys._MEIPASS
            else:
                app_path = os.path.dirname(sys.executable)
                if not os.path.exists(os.path.join(app_path, 'ZR.ico')):
                    internal_path = os.path.join(app_path, '_internal')
                    if os.path.exists(os.path.join(internal_path, 'ZR.ico')):
                        app_path = internal_path
        else:
            app_path = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.dirname(app_path)
        
        bg_path = os.path.join(app_path, 'ZR.png')
        if os.path.exists(bg_path):
            palette = self.palette()
            pixmap = QPixmap(bg_path)
            palette.setBrush(self.backgroundRole(), QBrush(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)))
            self.setPalette(palette)
