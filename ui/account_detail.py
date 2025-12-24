"""
账号详情对话框
用于单个账号的精细化管理：手动选课、单独执行、查看日志
"""
import os
import sys
import time
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QTextEdit, QMessageBox,
    QComboBox, QSpinBox, QSplitter, QWidget, QProgressBar, QCheckBox
)
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor
from PyQt5.QtMultimedia import QSound
from core.api import WeLearnClient
from core.account_manager import Account
from core.task_progress import TaskProgress



# 直接导入workers模块，避免使用ui.workers
import sys
import os

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 使用绝对导入
from ui import workers
LoginThread = workers.LoginThread
CourseThread = workers.CourseThread
UnitsThread = workers.UnitsThread
TimeStudyThread = workers.TimeStudyThread
StudyThread = workers.StudyThread


class AccountDetailDialog(QDialog):
    """
    账号详情对话框
    提供单个账号的完整控制：登录、选课、参数设置、执行任务
    """
    
    # 信号：状态更新（用于通知主界面刷新）
    status_updated = pyqtSignal(str, str, str)  # username, status, progress
    
    def __init__(self, account: Account, parent=None, resume_task_data=None):
        super().__init__(parent)
        self.account = account
        self.client = WeLearnClient()  # 每个账号独立的会话
        self.progress_manager = TaskProgress()  # 任务进度管理器
        self.resume_task_data = resume_task_data  # 恢复任务的数据
        self.need_resume_task = False  # 是否需要恢复任务
        self.auto_login_attempted = False  # 标记是否已尝试自动登录
        
        # 状态数据
        self.is_logged_in = False
        self.courses = []
        self.current_course = None
        self.current_units = []
        self.uid = ""
        self.classid = ""
        
        # 线程
        self.login_thread = None
        self.course_thread = None
        self.units_thread = None
        self.study_thread = None  # 刷作业/刷时长通用
        self.stats_thread = None  # 新增
        
        self.init_ui()
        self.setWindowTitle(f"账号管理 - {account.nickname or account.username}")
        self.setMinimumSize(700, 500)
        # 移除右上角的问号帮助按钮，并添加最小化按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowMinimizeButtonHint)
        self.set_background()
    
    def showEvent(self, event):
        """对话框显示时自动登录"""
        print(f"\n[AccountDetail] showEvent - 账号: {self.account.username}")
        print(f"  resume_task_data: {self.resume_task_data}")
        print(f"  is_logged_in: {self.is_logged_in}")
        print(f"  auto_login_attempted: {self.auto_login_attempted}")
        
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        super().showEvent(event)
        logger.info(f"账号详情对话框显示事件 - 账号: {self.account.username}")
        
        # 如果还没有尝试过自动登录，则自动登录
        if not self.auto_login_attempted and not self.is_logged_in:
            self.auto_login_attempted = True
            logger.info(f"准备自动登录 - 账号: {self.account.username}")
            print(f"  ✅ 准备自动登录")
            
            # 延迟一点时间再执行登录，确保界面完全显示
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(500, self.do_login)
            print(f"  ✅ 已安排500ms后执行登录")
            
            # 如果有恢复任务的数据，将在登录成功后自动恢复任务
            if self.resume_task_data:
                logger.info(f"检测到恢复任务数据，将在登录成功后恢复任务 - 账号: {self.account.username}")
                print(f"  ✅ 检测到恢复任务数据，将在登录成功后恢复")
                # 标记需要恢复任务，在课程和单元加载完成后自动恢复
                self.need_resume_task = True
        else:
            logger.info(f"已登录或已尝试登录，跳过自动登录 - 账号: {self.account.username}, 已登录: {self.is_logged_in}, 已尝试: {self.auto_login_attempted}")
            print(f"  ⚠️ 已登录或已尝试登录，跳过自动登录")
        
        print(f"[AccountDetail] showEvent 完成\n")
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # ========== 账号信息 ==========
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"<b>用户名:</b> {self.account.username}"))
        info_layout.addWidget(QLabel(f"<b>昵称:</b> {self.account.nickname or '无'}"))
        self.status_label = QLabel(f"<b>状态:</b> {self.account.status}")
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        
        self.login_btn = QPushButton("🔐 登录")
        self.login_btn.clicked.connect(self.do_login)
        info_layout.addWidget(self.login_btn)
        
        layout.addLayout(info_layout)
        
        # ========== 分割器：左侧课程选择 + 右侧日志 ==========
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：课程和设置
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 课程列表
        course_group = QGroupBox("课程列表")
        course_layout = QVBoxLayout(course_group)
        
        self.refresh_courses_btn = QPushButton("刷新课程")
        self.refresh_courses_btn.setEnabled(False)
        self.refresh_courses_btn.clicked.connect(self.refresh_courses)
        course_layout.addWidget(self.refresh_courses_btn)
        
        self.courses_list = QListWidget()
        self.courses_list.itemClicked.connect(self.on_course_selected)
        course_layout.addWidget(self.courses_list)
        
        left_layout.addWidget(course_group)
        
        # 任务设置
        settings_group = QGroupBox("任务设置")
        settings_layout = QVBoxLayout(settings_group)
        
        # 当前选中课程
        course_info_layout = QHBoxLayout()
        course_info_layout.addWidget(QLabel("目标课程:"))
        self.current_course_label = QLabel("未选择")
        self.current_course_label.setStyleSheet("color: #666; font-style: italic;")
        course_info_layout.addWidget(self.current_course_label)
        course_info_layout.addStretch()
        settings_layout.addLayout(course_info_layout)
        
        # 单元选择（复选框列表）
        unit_group = QGroupBox("选择单元")
        unit_group_layout = QVBoxLayout(unit_group)
        
        # 全选/取消全选按钮
        select_btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_none_btn = QPushButton("取消全选")
        self.select_all_btn.clicked.connect(self.select_all_units)
        self.select_none_btn.clicked.connect(self.select_none_units)
        select_btn_layout.addWidget(self.select_all_btn)
        select_btn_layout.addWidget(self.select_none_btn)
        select_btn_layout.addStretch()
        unit_group_layout.addLayout(select_btn_layout)
        
        # 单元列表
        self.unit_list = QListWidget()
        self.unit_list.setMaximumHeight(120)
        unit_group_layout.addWidget(self.unit_list)
        
        settings_layout.addWidget(unit_group)
        
        # === 模式选择 ===
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["刷作业", "刷时长"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        settings_layout.addLayout(mode_layout)
        
        # === 刷作业设置 ===
        self.homework_widget = QWidget()
        homework_layout = QVBoxLayout(self.homework_widget)
        homework_layout.setContentsMargins(0, 0, 0, 0)
        
        # 第一行：正确率设置
        homework_row1 = QHBoxLayout()
        homework_row1.addWidget(QLabel("正确率:"))
        
        # 固定正确率设置
        self.accuracy_spin = QSpinBox()
        self.accuracy_spin.setRange(0, 100)
        self.accuracy_spin.setValue(100)
        self.accuracy_spin.setSuffix("%")
        homework_row1.addWidget(self.accuracy_spin)
        
        # 正确率范围设置
        self.accuracy_range_checkbox = QCheckBox("启用范围")
        self.accuracy_range_checkbox.setToolTip("启用后将在指定范围内随机选择正确率")
        homework_row1.addWidget(self.accuracy_range_checkbox)
        
        self.accuracy_min_spin = QSpinBox()
        self.accuracy_min_spin.setRange(0, 100)
        self.accuracy_min_spin.setValue(80)
        self.accuracy_min_spin.setSuffix("%")
        self.accuracy_min_spin.setEnabled(False)  # 默认禁用
        homework_row1.addWidget(QLabel("最小:"))
        homework_row1.addWidget(self.accuracy_min_spin)
        
        self.accuracy_max_spin = QSpinBox()
        self.accuracy_max_spin.setRange(0, 100)
        self.accuracy_max_spin.setValue(100)
        self.accuracy_max_spin.setSuffix("%")
        self.accuracy_max_spin.setEnabled(False)  # 默认禁用
        homework_row1.addWidget(QLabel("最大:"))
        homework_row1.addWidget(self.accuracy_max_spin)
        
        homework_row1.addStretch()
        homework_layout.addLayout(homework_row1)
        
        # 第二行：并发数
        homework_row2 = QHBoxLayout()
        homework_row2.addWidget(QLabel("并发数:"))
        self.homework_concurrent_spin = QSpinBox()
        self.homework_concurrent_spin.setRange(1, 20)
        self.homework_concurrent_spin.setValue(5)
        self.homework_concurrent_spin.setToolTip("同时处理多少个课程，越高刷得越快")
        homework_row2.addWidget(self.homework_concurrent_spin)
        homework_row2.addStretch()
        homework_layout.addLayout(homework_row2)
        
        # 连接正确率范围复选框的信号
        self.accuracy_range_checkbox.stateChanged.connect(self.on_accuracy_range_changed)
        
        settings_layout.addWidget(self.homework_widget)
        
        # === 刷时长设置 ===
        self.time_widget = QWidget()
        time_layout = QVBoxLayout(self.time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        
        # 第一行：单元总时长
        time_row1 = QHBoxLayout()
        time_row1.addWidget(QLabel("单元时长:"))
        self.time_spin = QSpinBox()
        self.time_spin.setRange(1, 240)  # 最大240小时
        self.time_spin.setValue(3)  # 默认3小时
        self.time_spin.setToolTip("每个单元的总学习时长")
        time_row1.addWidget(self.time_spin)
        
        # 添加时间单位选择
        self.time_unit_combo = QComboBox()
        self.time_unit_combo.addItems(["小时", "分钟"])
        self.time_unit_combo.setCurrentText("小时")  # 默认选择小时
        self.time_unit_combo.currentTextChanged.connect(self.on_time_unit_changed)
        time_row1.addWidget(self.time_unit_combo)
        
        time_row1.addWidget(QLabel("  随机扰动:"))
        self.time_random_spin = QSpinBox()
        self.time_random_spin.setRange(0, 30)
        self.time_random_spin.setValue(5)
        self.time_random_spin.setSuffix(" 分钟")
        self.time_random_spin.setToolTip("随机增减范围，如设5则实际时长为 55~65 分钟")
        time_row1.addWidget(self.time_random_spin)
        time_row1.addStretch()
        time_layout.addLayout(time_row1)
        
        # 第二行：并发数
        time_row2 = QHBoxLayout()
        time_row2.addWidget(QLabel("并发数:"))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 100)
        self.concurrent_spin.setValue(90)
        self.concurrent_spin.setToolTip("同时刷多少个课程，越高刷得越快")
        time_row2.addWidget(self.concurrent_spin)
        time_row2.addStretch()
        time_layout.addLayout(time_row2)
        
        settings_layout.addWidget(self.time_widget)
        self.time_widget.hide()  # 默认显示刷作业
        
        left_layout.addWidget(settings_group)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ 开始刷作业")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_study)
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_study)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        left_layout.addLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(left_widget)
        
        # 右侧：日志
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(200, 200, 200, 200);
                border-radius: 5px;
                padding: 5px;
                color: #333333;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        
        right_layout.addWidget(log_group)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([350, 350])
        layout.addWidget(splitter)
    
    def log(self, message: str):
        """添加日志"""
        # 添加到UI日志
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
        # 同时记录到全局日志系统
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        logger.info(message)
    

    def update_status(self, status: str, progress: str = ""):
        """更新状态并通知主界面"""
        self.account.status = status
        self.account.progress = progress
        self.status_label.setText(f"<b>状态:</b> {status}")
        self.status_updated.emit(self.account.username, status, progress)
    
    def do_login(self):
        """执行登录"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        if self.is_logged_in:
            logger.info("已经登录，跳过重复登录")
            return

        logger.info(f"开始登录 - 账号: {self.account.username}")
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        self.update_status("正在登录...")

        # 创建登录线程
        self.login_thread = LoginThread(
            self.client,
            self.account.username,
            self.account.password
        )

        # 连接信号
        self.login_thread.login_result.connect(self.on_login_result)

        # 启动线程
        self.login_thread.start()
    
    def on_login_result(self, success: bool, message: str, user_id: str = ""):
        """登录结果回调"""
        print(f"\n[AccountDetail] on_login_result - 账号: {self.account.username}")
        print(f"  success: {success}")
        print(f"  message: {message}")
        print(f"  user_id: {user_id}")
        print(f"  resume_task_data: {self.resume_task_data}")
        
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        self.login_btn.setEnabled(True)
        
        if success:
            self.is_logged_in = True
            self.login_btn.setText("✅ 已登录")
            self.login_btn.setEnabled(False)
            self.refresh_courses_btn.setEnabled(True)
            
            # 存储用户ID
            if user_id:
                self.uid = user_id
                self.log(f"✅ 登录成功，用户ID: {user_id}")
                logger.info(f"登录成功，用户ID: {user_id} - 账号: {self.account.username}")
                print(f"[DEBUG] 用户ID已设置: {self.uid}")  # 添加这行
                if hasattr(self, 'user_id_label'):
                    self.user_id_label.setText(f"用户ID: {user_id}")
            else:
                self.log(f"✅ 登录成功，但未能获取用户ID")
                logger.warning(f"登录成功但未能获取用户ID - 账号: {self.account.username}")
                print(f"[DEBUG] 登录返回的uid为空")  # 添加这行
            
            print(f"  ✅ 登录成功，更新UI状态")
            self.update_status("已登录")
            
            # 自动刷新课程
            print(f"  ✅ 准备刷新课程")
            self.refresh_courses()
            
            # 如果有恢复任务的数据，登录成功后立即恢复任务
            if self.resume_task_data:
                logger.info(f"检测到恢复任务数据，将在课程刷新后恢复任务 - 账号: {self.account.username}")
                print(f"  ✅ 检测到恢复任务数据，将在课程刷新后恢复")
                # 标记需要恢复任务，在课程和单元加载完成后自动恢复
                self.need_resume_task = True
                
                # 使用定时器确保对话框在前台
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, self._ensure_foreground_and_resume)
                print(f"  ✅ 已安排1000ms后确保前台并恢复任务")
                
                # 延迟一段时间后尝试恢复任务，确保课程刷新开始
                QTimer.singleShot(2000, self._try_resume_task)
        else:
            self.login_btn.setText("🔐 登录")
            self.log(f"❌ 登录失败: {message}")
            logger.error(f"登录失败 - 账号: {self.account.username}, 错误: {message}")
            self.update_status("登录失败", message)
            msg_box = QMessageBox(QMessageBox.Warning, "登录失败", message)
            # 移除问号帮助按钮
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
    
    def _ensure_foreground_and_resume(self):
        """确保对话框在前台，然后开始恢复流程"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        try:
            # 确保窗口在前台
            self.raise_()
            self.activateWindow()
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)

            logger.info(f"确保对话框在前台 - 账号: {self.account.username}")

            # 检查是否需要恢复任务
            if self.need_resume_task and self.resume_task_data:
                logger.info(f"开始执行任务恢复流程 - 账号: {self.account.username}")
                # 自动刷新课程，这会触发单元获取，然后自动恢复任务
                if hasattr(self, 'refresh_courses') and callable(self.refresh_courses):
                    self.refresh_courses()
                else:
                    logger.error("缺少 refresh_courses 方法！")
            else:
                logger.info(f"不需要恢复任务 - 账号: {self.account.username}")

        except Exception as e:
            logger.error(f"确保前台和恢复任务时出错: {str(e)}", exc_info=True)
            
    def _ensure_foreground_after_resume(self):
        """确保任务恢复后窗口在前台"""
        try:
            self.raise_()
            self.activateWindow()
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("AccountDetail")
            logger.error(f"确保前台时出错: {str(e)}")
            
    def _ensure_foreground_and_resume_old(self):
        """确保对话框在前台并准备恢复任务"""
        try:
            self.raise_()
            self.activateWindow()
            from core.logger import get_logger
            logger = get_logger("AccountDetail")
            logger.info(f"已确保账号详情对话框在前台显示 - 账号: {self.account.username}")
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("AccountDetail")
            logger.error(f"确保对话框在前台显示时出错: {str(e)}")
    
    def _try_resume_task(self):
        """尝试恢复任务"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        try:
            if self.need_resume_task and self.resume_task_data:
                logger.info(f"尝试恢复任务 - 账号: {self.account.username}")
                self.resume_task()
        except Exception as e:
            logger.error(f"尝试恢复任务时出错: {str(e)}", exc_info=True)
    
    def refresh_courses(self):
        """刷新课程列表"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        if not self.is_logged_in:
            logger.warning("未登录，无法刷新课程")
            self.log("❌ 请先登录")
            return

        logger.info(f"开始刷新课程 - 账号: {self.account.username}")
        self.refresh_courses_btn.setEnabled(False)
        self.refresh_courses_btn.setText("刷新中...")
        self.update_status("正在获取课程列表...")

        # 创建课程线程
        self.course_thread = CourseThread(self.client)

        # 连接信号
        self.course_thread.course_result.connect(self.on_course_result)

        # 启动线程
        self.course_thread.start()
    
    def on_course_result(self, success: bool, data: list, message: str):
        """课程列表结果回调"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        self.refresh_courses_btn.setEnabled(True)
        self.refresh_courses_btn.setText("刷新课程")

        if success:
            self.courses = data

            # 检查是否已有用户ID（从登录时获取）
            if hasattr(self, 'uid') and self.uid:
                # 使用登录时获取的用户ID
                uid = self.uid
                logger.info(f"使用登录时获取的用户ID: {uid} - 账号: {self.account.username}")
            else:
                # 尝试获取用户ID
                success_get_uid, uid, uid_message = self.client.get_user_id()
                if not success_get_uid:
                    self.log(f"⚠️ 获取用户ID失败: {uid_message}")
                    logger.warning(f"获取用户ID失败 - 账号: {self.account.username}, 错误: {uid_message}")
                    # 即使获取用户ID失败，也继续加载课程列表，但不显示学习时长
                    self.courses_list.clear()
                    course_names = []
                    for course in self.courses:
                        progress = course.get('per', '未知')
                        # 显示课程信息，但不包含学习时长
                        item = QListWidgetItem(f"{course['name']} (进度: {progress}%)")
                        item.setData(Qt.ItemDataRole.UserRole, course)
                        self.courses_list.addItem(item)
                        course_names.append(course['name'])
                    
                    self.log(f"✅ 获取到 {len(self.courses)} 门课程")
                    logger.info(f"课程列表获取成功 - 账号: {self.account.username}, 课程: {', '.join(course_names)}")
                    
                    # 如果是从任务恢复进来的，自动选中对应课程
                    if self.resume_task_data and self.need_resume_task:
                        target_cid = self.resume_task_data.get('cid')
                        for i in range(self.courses_list.count()):
                            item = self.courses_list.item(i)
                            course = item.data(Qt.ItemDataRole.UserRole)
                            if course and course['cid'] == target_cid:
                                self.courses_list.setCurrentItem(item)
                                self.current_course = course
                                self.current_course_label.setText(course['name'])
                                self.get_units()
                                break
                    return

            # 设置用户ID
            self.uid = uid

            # 填充课程列表
            self.courses_list.clear()
            course_names = []
            for course in self.courses:
                # 获取课程进度，如果没有则显示未知
                progress = course.get('per', '未知')
                item = QListWidgetItem(f"{course['name']} (进度: {progress}%)")
                item.setData(Qt.ItemDataRole.UserRole, course)
                self.courses_list.addItem(item)
                course_names.append(course['name'])

            self.log(f"✅ 获取到 {len(self.courses)} 门课程")
            logger.info(f"课程列表获取成功 - 账号: {self.account.username}, 课程: {', '.join(course_names)}")

            # 如果是从任务恢复进来的，自动选中对应课程
            if self.resume_task_data and self.need_resume_task:
                target_cid = self.resume_task_data.get('cid')
                for i in range(self.courses_list.count()):
                    item = self.courses_list.item(i)
                    course = item.data(Qt.ItemDataRole.UserRole)
                    if course and course['cid'] == target_cid:
                        self.courses_list.setCurrentItem(item)
                        self.current_course = course
                        self.current_course_label.setText(course['name'])
                        # 自动获取单元
                        self.get_units()
                        break
        else:
            self.log(f"❌ 获取课程失败: {message}")
            logger.error(f"课程列表获取失败 - 账号: {self.account.username}, 错误: {message}")
    


    def on_courses_result(self, success: bool, courses: list, message: str):
        """课程列表结果回调"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        self.refresh_courses_btn.setEnabled(True)
        self.refresh_courses_btn.setText("刷新课程")
        
        if success:
            self.courses = courses
            self.courses_list.clear()
            course_names = []
            for course in courses:
                item = QListWidgetItem(f"{course['name']} (进度: {course['per']}%)")
                item.setData(Qt.ItemDataRole.UserRole, course)
                self.courses_list.addItem(item)
                course_names.append(course['name'])
            self.log(f"✅ 获取到 {len(courses)} 门课程")
            logger.info(f"课程列表获取成功 - 账号: {self.account.username}, 课程数量: {len(courses)}, 课程: {', '.join(course_names)}")
        else:
            self.log(f"❌ 获取课程失败: {message}")
            logger.error(f"课程列表获取失败 - 账号: {self.account.username}, 错误: {message}")
            msg_box = QMessageBox(QMessageBox.Warning, "失败", message)
            # 移除问号帮助按钮
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
    
    def on_course_selected(self, item: QListWidgetItem):
        """选择课程"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        course = item.data(Qt.ItemDataRole.UserRole)
        self.current_course = course
        course_name = course['name']
        course_id = course['cid']
        
        logger.info(f"选择课程 - 账号: {self.account.username}, 课程: {course_name} (ID: {course_id})")
        
        self.current_course_label.setText(course_name)
        self.log(f"选择课程: {course_name}")
        
        # 获取单元信息
        logger.info(f"开始获取单元信息 - 账号: {self.account.username}, 课程ID: {course_id}")
        self.get_units()
    
    def get_units(self):
        """获取单元列表"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        if not self.current_course:
            logger.warning("没有选择课程，无法获取单元")
            self.log("❌ 请先选择课程")
            return

        if not self.is_logged_in:
            logger.warning("未登录，无法获取单元")
            self.log("❌ 请先登录")
            return

        logger.info(f"开始获取单元 -课程: {self.current_course['name']}")
        self.unit_list.clear()
        self.start_btn.setEnabled(False)
        self.update_status(f"正在获取 {self.current_course['name']} 的单元...")

        # 创建单元线程
        self.units_thread = UnitsThread(
            self.client,
            self.current_course['cid']
        )

        # 连接信号
        self.units_thread.units_result.connect(self.on_units_result)

        # 启动线程
        self.units_thread.start()
    
    def on_units_result(self, success: bool, units_data: dict, message: str):
        """单元信息结果回调"""
        print(f"\n[AccountDetail] on_units_result - 账号: {self.account.username}")
        print(f"  success: {success}")
        print(f"  need_resume_task: {self.need_resume_task}")
        print(f"  resume_task_data: {self.resume_task_data is not None}")
        
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        if success and units_data:
            # units_data 已经是字典，不需要索引访问
            data = units_data
            self.uid = data['uid']
            self.classid = data['classid']
            self.current_units = data['units']
            print(f"  ✅ 成功获取单元数据，共 {len(self.current_units)} 个单元")
            
            # 填充复选框列表
            self.unit_list.clear()
            unit_names = []
            for i, unit in enumerate(self.current_units):
                unit_name = unit.get('name', f'单元 {i+1}')
                item = QListWidgetItem(f"单元 {i+1}: {unit_name}")
                item.setCheckState(Qt.CheckState.Checked)  # 默认全选
                item.setData(Qt.ItemDataRole.UserRole, i)  # 存储索引
                self.unit_list.addItem(item)
                unit_names.append(unit_name)
            
            self.start_btn.setEnabled(True)
            self.log(f"✅ 获取到 {len(self.current_units)} 个单元")
            logger.info(f"单元列表获取成功 - 账号: {self.account.username}, 课程: {self.current_course['name']}, 单元数量: {len(self.current_units)}, 单元: {', '.join(unit_names)}")
            print(f"  ✅ 单元列表已填充，启用开始按钮")
            
            # 如果需要恢复任务，现在开始恢复
            if self.need_resume_task and self.resume_task_data:
                logger.info(f"课程和单元数据已加载完成，开始恢复任务")
                print(f"  ✅ 检测到需要恢复任务，准备调用resume_task")
                # 使用单次定时器确保UI更新完成后再恢复任务
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(500, self._try_resume_task)
        else:
            self.log(f"❌ 获取单元失败: {message}")
            logger.error(f"单元列表获取失败 - 账号: {self.account.username}, 课程: {self.current_course['name']}, 错误: {message}")
    
    def select_all_units(self):
        """全选单元"""
        for i in range(self.unit_list.count()):
            self.unit_list.item(i).setCheckState(Qt.CheckState.Checked)
    
    def select_none_units(self):
        """取消全选单元"""
        for i in range(self.unit_list.count()):
            self.unit_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    
    def on_mode_changed(self, mode: str):
        """模式切换"""
        if mode == "刷作业":
            self.homework_widget.show()
            self.time_widget.hide()
            self.start_btn.setText("▶️ 开始刷作业")
        else:
            self.homework_widget.hide()
            self.time_widget.show()
            self.start_btn.setText("▶️ 开始刷时长")
    
    def on_time_unit_changed(self, unit: str):
        """时间单位切换"""
        current_value = self.time_spin.value()
        
        if unit == "小时":
            # 从分钟转换为小时
            self.time_spin.setRange(1, 240)  # 最大240小时
            self.time_spin.setValue(max(1, current_value // 60))  # 转换为小时，确保至少1小时
            self.time_random_spin.setSuffix(" 分钟")  # 随机扰动始终以分钟为单位
        else:
            # 从小时转换为分钟
            self.time_spin.setRange(1, 14400)  # 最大14400分钟
            self.time_spin.setValue(max(1, current_value * 60))  # 转换为分钟，确保至少1分钟
            self.time_random_spin.setSuffix(" 分钟")  # 随机扰动始终以分钟为单位
    
    def start_study(self):
        """开始任务"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        logger.info(f"开始执行任务 - 账号: {self.account.username}")
        
        if not self.current_course:
            logger.warning("未选择课程，任务终止")
            msg_box = QMessageBox(QMessageBox.Warning, "警告", "请先选择课程")
            # 移除问号帮助按钮
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
            return
        
        logger.info(f"已选择课程: {self.current_course['name']} (ID: {self.current_course['cid']})")
        
        # 获取选中的单元
        units_to_process = []
        for i in range(self.unit_list.count()):
            item = self.unit_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                unit_index = item.data(Qt.ItemDataRole.UserRole)
                unit_data = self.current_units[unit_index] if unit_index < len(self.current_units) else {}
                units_to_process.append(unit_index)
                logger.info(f"选中单元: {unit_data.get('name', f'单元 {unit_index+1}')} (索引: {unit_index})")
        
        if not units_to_process:
            logger.warning("未选择任何单元，任务终止")
            msg_box = QMessageBox(QMessageBox.Warning, "警告", "请至少选择一个单元")
            # 移除问号帮助按钮
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
            return
        
        mode = self.mode_combo.currentText()
        logger.info(f"任务模式: {mode}")
        
        # 添加任务开始前的提醒
        if mode == "刷作业":
            msg_box = QMessageBox(QMessageBox.Information, "任务提醒", 
                                 f"即将开始刷作业任务\n\n课程: {self.current_course['name']}\n选中单元数: {len(units_to_process)} 个\n\n确认要开始吗？")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            # 移除问号帮助按钮
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            if msg_box.exec_() != QMessageBox.Yes:
                logger.info("用户取消了刷作业任务")
                return
        else:
            # 获取时间值和单位
            time_value = self.time_spin.value()
            time_unit = self.time_unit_combo.currentText()
            
            # 转换为分钟
            if time_unit == "小时":
                total_minutes = time_value * 60
                time_text = f"{time_value} 小时"
            else:
                total_minutes = time_value
                time_text = f"{time_value} 分钟"
                
            random_range = self.time_random_spin.value()
            concurrent = self.concurrent_spin.value()
            
            # 计算预计完成时间
            estimated_time = total_minutes * len(units_to_process) / concurrent
            hours = int(estimated_time // 60)
            minutes = int(estimated_time % 60)
            seconds = int((estimated_time * 60) % 60)
            
            if hours > 0:
                time_estimate = f"{hours} 小时 {minutes} 分钟 {seconds} 秒"
            else:
                time_estimate = f"{minutes} 分钟 {seconds} 秒"
            
            msg_box = QMessageBox(QMessageBox.Information, "任务提醒", 
                                 f"即将开始刷时长任务\n\n课程: {self.current_course['name']}\n选中单元数: {len(units_to_process)} 个\n每单元时长: {time_text}\n预计完成时间: {time_estimate}\n\n确认要开始吗？")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            # 移除问号帮助按钮
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            if msg_box.exec_() != QMessageBox.Yes:
                logger.info("用户取消了刷时长任务")
                return
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        if mode == "刷作业":
            # 根据复选框状态决定正确率配置
            if self.accuracy_range_checkbox.isChecked():
                # 使用正确率范围
                accuracy_config = (self.accuracy_min_spin.value(), self.accuracy_max_spin.value())
                logger.info(f"刷作业配置 - 正确率范围: {accuracy_config[0]}%-{accuracy_config[1]}%, 并发数: {homework_concurrent}")
            else:
                # 使用固定正确率
                accuracy_config = self.accuracy_spin.value()
                logger.info(f"刷作业配置 - 正确率: {accuracy_config}%, 并发数: {homework_concurrent}")
            
            homework_concurrent = self.homework_concurrent_spin.value()
            self.log(f"开始刷作业 (已选 {len(units_to_process)} 个单元, {homework_concurrent} 并发)...")
            self.update_status("运行中")
            
            logger.info(f"创建刷作业线程 - 课程ID: {self.current_course['cid']}, 用户ID: {self.uid}, 班级ID: {self.classid}")
            # 生成任务ID
            task_id = f"刷作业_{self.current_course['cid']}_{self.uid}_{int(time.time())}"
            
            # 如果是从恢复任务开始的，立即删除旧的进度
            if self.resume_task_data:
                old_task_id = self.resume_task_data.get('task_id')
                if old_task_id:
                    success = self.progress_manager.clear_task_progress(old_task_id)
                    if success:
                        self.log(f"✅ 已删除旧的进度: {old_task_id}")
                        logger.info(f"已删除旧的进度: {old_task_id}")
                    else:
                        self.log(f"⚠️ 删除旧进度失败: {old_task_id}")
                        logger.error(f"删除旧进度失败: {old_task_id}")
            
            self.study_thread = StudyThread(
                self.client,
                self.current_course['cid'],
                self.uid,
                self.classid,
                units_to_process,  # 传入单元列表
                accuracy_config,
                self.current_units,
                max_concurrent=homework_concurrent,  # 传入并发数
                username=self.account.username,  # 添加用户名
                task_id=task_id  # 添加任务ID
            )
        else:
            # 获取时间值和单位（这些变量在提醒弹窗中已经获取过）
            time_value = self.time_spin.value()
            time_unit = self.time_unit_combo.currentText()
            
            # 转换为分钟
            if time_unit == "小时":
                total_minutes = time_value * 60
            else:
                total_minutes = time_value
                
            random_range = self.time_random_spin.value()
            concurrent = self.concurrent_spin.value()
            
            logger.info(f"刷时长配置 - 每单元时长: {time_value} {time_unit}, 随机范围: ±{random_range} 分钟, 并发数: {concurrent}")
            
            # 根据选择的时间单位显示日志
            if time_unit == "小时":
                self.log(f"开始刷时长 (已选 {len(units_to_process)} 个单元, 每单元 {time_value}±{random_range//60} 小时, {concurrent} 并发)...")
            else:
                self.log(f"开始刷时长 (已选 {len(units_to_process)} 个单元, 每单元 {time_value}±{random_range} 分钟, {concurrent} 并发)...")
                
            self.update_status("运行中")
            
            logger.info(f"创建刷时长线程 - 课程ID: {self.current_course['cid']}, 用户ID: {self.uid}, 班级ID: {self.classid}")
            # 生成任务ID
            task_id = f"刷时长_{self.current_course['cid']}_{self.uid}_{int(time.time())}"
            
            # 如果是从恢复任务开始的，立即删除旧的进度
            if self.resume_task_data:
                old_task_id = self.resume_task_data.get('task_id')
                if old_task_id:
                    success = self.progress_manager.clear_task_progress(old_task_id)
                    if success:
                        self.log(f"✅ 已删除旧的进度: {old_task_id}")
                        logger.info(f"已删除旧的进度: {old_task_id}")
                    else:
                        self.log(f"⚠️ 删除旧进度失败: {old_task_id}")
                        logger.error(f"删除旧进度失败: {old_task_id}")
            
            self.study_thread = TimeStudyThread(
                self.client,
                self.current_course['cid'],
                self.uid,
                self.classid,
                units_to_process,  # 传入单元列表
                total_minutes,     # 每单元总分钟数
                random_range,      # 随机扰动分钟数
                self.current_units,
                max_concurrent=concurrent,
                username=self.account.username,  # 添加用户名
                task_id=task_id  # 添加任务ID
            )
        
        logger.info("任务线程创建完成，连接信号并启动")
        self.study_thread.progress_update.connect(self.handle_progress_update)
        self.study_thread.study_finished.connect(self.on_study_finished)
        self.study_thread.start()
    
    def stop_study(self):
        """停止任务"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        logger.info(f"用户请求停止任务 - 账号: {self.account.username}, 课程: {self.current_course['name'] if self.current_course else '未选择'}")
        
        if self.study_thread and self.study_thread.isRunning():
            self.log("正在停止任务...")
            logger.info("正在发送停止信号给任务线程")
            
            # 调用线程的stop方法，这会保存进度
            self.study_thread.stop()
            
            # 等待线程结束，最多等待5秒
            self.study_thread.wait(5000)
            
            if self.study_thread.isRunning():
                logger.warning("任务线程在5秒后仍在运行，强制终止")
                self.log("任务未能正常停止，强制终止")
                self.study_thread.terminate()
                self.study_thread.wait(2000)  # 再等待2秒
                
                # 如果仍在运行，使用更强制的方法
                if self.study_thread.isRunning():
                    logger.error("任务线程强制终止失败，使用最终方法")
                    self.log("任务线程无法终止，正在使用最终方法")
                    import os
                    import signal
                    try:
                        # 尝试使用系统信号终止
                        os.kill(self.study_thread.threadId(), signal.SIGTERM)
                    except:
                        pass
            else:
                logger.info("任务线程已正常停止")
                self.log("任务已停止")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.log("⏹️ 任务已停止")
        self.update_status("已停止")
    
    def handle_progress_update(self, status_type: str, message: str):
        """处理学习进度更新"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        if status_type == "start":
            self.log(f"开始: {message}")
        elif status_type == "finish":
            self.log(f"完成: {message}")
        elif status_type == "skip":
            self.log(f"跳过: {message}")
        elif status_type == "completed":
            self.log(f"已完成: {message}")
        elif status_type == "error":
            self.log(f"错误: {message}")
        elif status_type == "unit_start":
            self.log(message)
        elif status_type == "unit_finish":
            self.log(message)
        elif status_type == "info":
            self.log(f"信息: {message}")
        else:
            self.log(message)
    
    def on_study_finished(self, result: dict):
        """任务完成回调"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        mode = self.mode_combo.currentText()
        if mode == "刷作业":
            way1_success = result.get('way1_succeed', 0)
            way1_failed = result.get('way1_failed', 0)
            way2_success = result.get('way2_succeed', 0)
            way2_failed = result.get('way2_failed', 0)
            
            # 计算成功率
            total_way1 = way1_success + way1_failed
            total_way2 = way2_success + way2_failed
            way1_rate = f"{(way1_success/total_way1*100):.1f}%" if total_way1 > 0 else "0%"
            way2_rate = f"{(way2_success/total_way2*100):.1f}%" if total_way2 > 0 else "0%"
            
            # 创建更友好的统计信息
            msg = f"📊 刷作业任务完成统计:\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"📝 步骤1 (视频/文档): 成功 {way1_success} 个, 失败 {way1_failed} 个 (成功率: {way1_rate})\n"
            msg += f"✏️  步骤2 (测验/作业): 成功 {way2_success} 个, 失败 {way2_failed} 个 (成功率: {way2_rate})\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"🎯 总计: 成功 {way1_success + way2_success} 个, 失败 {way1_failed + way2_failed} 个"
            
            self.log(f"✅ 刷作业完成！\n{msg}")
            logger.info(f"刷作业任务完成 - 账号: {self.account.username}, 课程: {self.current_course['name']}, 步骤1: {way1_success}/{total_way1}, 步骤2: {way2_success}/{total_way2}")
        else:
            completed_units = result.get('completed_units', 0)
            # 获取选中的单元数量，而不是所有单元数量
            total_units = len(self.study_thread.unit_idx) if hasattr(self.study_thread, 'unit_idx') and self.study_thread.unit_idx else (len(self.current_units) if self.current_units else 0)
            completion_rate = f"{(completed_units/total_units*100):.1f}%" if total_units > 0 else "0%"
            
            msg = f"📊 刷时长任务完成统计:\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"⏰ 已完成单元: {completed_units}/{total_units} (完成率: {completion_rate})\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"🎯 任务已全部完成"
            
            self.log(f"✅ 刷时长完成！\n{msg}")
            logger.info(f"刷时长任务完成 - 账号: {self.account.username}, 课程: {self.current_course['name']}, 完成单元: {completed_units}/{total_units}")
        
        # 标记任务为已完成
        if hasattr(self, 'study_thread') and self.study_thread and hasattr(self.study_thread, 'task_id') and self.study_thread.task_id:
            self.progress_manager.mark_task_completed(self.study_thread.task_id)
            logger.info(f"任务已标记为完成 - 任务ID: {self.study_thread.task_id}")
        
        # 播放提示音
        try:
            # 尝试使用系统默认提示音
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except Exception as e:
            self.log(f"播放系统提示音失败: {str(e)}")
            # 如果系统提示音失败，尝试使用PyQt5的QSound
            try:
                # 尝试播放系统默认声音
                QSound.play("SystemExclamation")
            except Exception as e2:
                self.log(f"播放QSound提示音也失败: {str(e2)}")
        
        self.update_status("已完成")
        msg_box = QMessageBox(QMessageBox.Information, "完成", "任务已完成！")
        # 移除问号帮助按钮
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.exec_()
        
        # 清理线程引用
        self.study_thread = None
        logger.debug("任务线程引用已清理")
    
    def on_accuracy_range_changed(self, state):
        """处理正确率范围复选框状态变化"""
        is_checked = state == 2  # Qt.Checked = 2
        
        if is_checked:
            # 启用范围设置，禁用固定正确率
            self.accuracy_spin.setEnabled(False)
            self.accuracy_min_spin.setEnabled(True)
            self.accuracy_max_spin.setEnabled(True)
        else:
            # 禁用范围设置，启用固定正确率
            self.accuracy_spin.setEnabled(True)
            self.accuracy_min_spin.setEnabled(False)
            self.accuracy_max_spin.setEnabled(False)
    
    def closeEvent(self, event):
        """关闭窗口时清理线程"""
        from core.logger import get_logger
        import threading
        import time
        import os
        
        logger = get_logger("AccountDetail")
        
        # 检查是否有任务正在运行
        if self.study_thread and self.study_thread.isRunning():
            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认关闭",
                "当前有任务正在进行中，关闭此页面将终止任务。\n\n是否确认继续关闭？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                # 用户选择不关闭，忽略关闭事件
                event.ignore()
                return
            
            # 用户确认关闭，记录日志
            logger.info(f"用户确认关闭，将终止正在进行的任务 - 账号: {self.account.username}")
        
        try:
            import psutil
        except ImportError:
            psutil = None
        
        logger.info(f"账号详情窗口关闭 - 账号: {self.account.username}")
        logger.info(f"当前进程ID: {os.getpid()}")
        logger.info(f"当前线程ID: {threading.get_ident()}")
        logger.info(f"活动线程数: {threading.active_count()}")
        
        # 记录所有活动线程
        for thread in threading.enumerate():
            logger.info(f"活动线程: {thread.name} (ID: {thread.ident}, 是否运行中: {thread.is_alive()})")
        
        # 记录进程状态
        if psutil is not None:
            try:
                process = psutil.Process(os.getpid())
                logger.info(f"进程状态: {process.status()}")
                logger.info(f"进程内存使用: {process.memory_info().rss / 1024 / 1024:.2f} MB")
                logger.info(f"进程CPU使用率: {process.cpu_percent()}%")
                logger.info(f"进程线程数: {process.num_threads()}")
            except Exception as e:
                logger.error(f"获取进程状态失败: {str(e)}")
        else:
            logger.warning("psutil模块不可用，无法获取详细进程信息")
        
        # 先发送停止信号
        if self.study_thread:
            try:
                logger.info(f"任务线程状态: {self.study_thread.isRunning()}")
                logger.info(f"任务线程是否已停止: {self.study_thread.isFinished()}")
                
                if hasattr(self.study_thread, 'stop'):
                    logger.info("调用线程stop方法")
                    self.study_thread.stop()
                    
                if self.study_thread.isRunning():
                    logger.warning("关闭窗口时发现仍在运行的任务，尝试停止")
                    self.log("正在停止任务...")
                    
                    # 使用quit而不是terminate，确保线程能够正常清理
                    logger.info("调用线程quit方法")
                    self.study_thread.quit()
                    
                    # 增加等待时间，确保线程有足够时间停止
                    logger.info("等待线程停止（3秒）")
                    start_time = time.time()
                    if not self.study_thread.wait(3000):
                        wait_time = time.time() - start_time
                        logger.warning(f"任务线程未能正常停止（等待了{wait_time:.2f}秒），强制终止")
                        self.study_thread.terminate()
                        logger.info("调用线程terminate方法")
                        
                        start_time = time.time()
                        if not self.study_thread.wait(1000):
                            wait_time = time.time() - start_time
                            logger.error(f"强制终止失败（等待了{wait_time:.2f}秒）")
                    
                    # 再次检查，如果还在运行，使用更强制的方式
                    if self.study_thread.isRunning():
                        logger.error("任务线程仍在运行，使用最强制的方式终止")
                        try:
                            # 尝试强制结束线程
                            self.study_thread.terminate()
                            logger.info("再次调用线程terminate方法")
                            # 立即等待，不给线程任何反应时间
                            start_time = time.time()
                            if not self.study_thread.wait(500):
                                wait_time = time.time() - start_time
                                logger.error(f"无法终止任务线程（等待了{wait_time:.2f}秒），程序可能无法正常退出")
                        except Exception as term_error:
                            logger.error(f"强制终止线程时出错: {str(term_error)}")
                
                # 确保线程完全清理
                if self.study_thread:
                    self.study_thread.deleteLater()
                self.study_thread = None
                logger.debug("任务线程已清理")
            except Exception as e:
                logger.error(f"清理任务线程时出错: {str(e)}")
                # 即使出错也要继续清理
                self.study_thread = None
        
        # 关闭客户端连接
        if hasattr(self, 'client') and self.client:
            try:
                # 如果客户端有清理方法，调用它
                if hasattr(self.client, 'close'):
                    self.client.close()
                logger.debug("客户端连接已关闭")
            except Exception as e:
                logger.error(f"关闭客户端连接时出错: {str(e)}")
        
        # 再次记录线程状态
        logger.info(f"关闭后活动线程数: {threading.active_count()}")
        for thread in threading.enumerate():
            logger.info(f"关闭后活动线程: {thread.name} (ID: {thread.ident}, 是否运行中: {thread.is_alive()})")
        
        logger.info(f"账号详情窗口已关闭 - 账号: {self.account.username}")
        event.accept()
    
    def set_background(self):
        # 获取应用程序路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的应用程序
            if hasattr(sys, '_MEIPASS'):
                # 单文件版本，资源文件在临时目录中
                app_path = sys._MEIPASS
            else:
                # 目录版本
                app_path = os.path.dirname(sys.executable)
                # 检查资源文件是否在根目录
                if not os.path.exists(os.path.join(app_path, 'ZR.png')):
                    # 如果不在根目录，尝试在_internal目录中查找
                    internal_path = os.path.join(app_path, '_internal')
                    if os.path.exists(os.path.join(internal_path, 'ZR.png')):
                        app_path = internal_path
        else:
            # 如果是开发环境
            app_path = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.dirname(app_path)  # 回到项目根目录
        
        # 设置背景图片
        bg_path = os.path.join(app_path, 'ZR.png')
        print(f"背景图片路径: {bg_path}")
        print(f"背景图片是否存在: {os.path.exists(bg_path)}")
        
        if os.path.exists(bg_path):
            try:
                pixmap = QPixmap(bg_path)
                if not pixmap.isNull():
                    palette = self.palette()
                    palette.setBrush(self.backgroundRole(), QBrush(pixmap.scaled(
                        self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)))
                    self.setPalette(palette)
                    print("背景图片设置成功")
                else:
                    print("背景图片加载失败，图片可能损坏")
            except Exception as e:
                print(f"设置背景图片时发生错误: {str(e)}")
        else:
            print("背景图片文件不存在，跳过背景设置")
    
    def resizeEvent(self, event):
        # 窗口大小改变时重新设置背景
        self.set_background()
        super().resizeEvent(event)
    
    def resume_task(self):
        """恢复任务"""
        print(f"\n[AccountDetail] resume_task - 账号: {self.account.username}")
        print(f"  resume_task_data: {self.resume_task_data}")
        print(f"  is_logged_in: {self.is_logged_in}")
        print(f"  courses: {len(self.courses) if self.courses else 0}")
        
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        try:
            if not self.resume_task_data:
                logger.warning("没有恢复任务数据")
                print(f"  ❌ 没有恢复任务数据")
                return
            
            if not self.is_logged_in:
                logger.warning("账号未登录，无法恢复任务")
                print(f"  ⚠️ 账号未登录，1秒后重试")
                # 延迟1秒后再次尝试
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, self.resume_task)
                return
            
            # 检查课程数据是否已加载
            if not self.courses:
                logger.warning("课程数据未加载，无法恢复任务")
                print(f"  ⚠️ 课程数据未加载，1秒后重试")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, self.resume_task)
                return
            
            # 检查UI是否已完全加载课程列表
            if self.courses_list.count() == 0:
                logger.warning("课程列表UI未加载，无法恢复任务")
                print(f"  ⚠️ 课程列表UI未加载，1秒后重试")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, self.resume_task)
                return
            
            task_id = self.resume_task_data.get('task_id', '未知ID')
            task_type = self.resume_task_data.get('task_type', '未知任务')
            logger.info(f"开始恢复任务 - 账号: {self.account.username}, 任务ID: {task_id}")
            print(f"  ✅ 开始恢复任务: {task_type} (ID: {task_id})")
            self.log(f"正在恢复任务: {task_type}")
            
            # 确保对话框在前台
            self.raise_()
            self.activateWindow()
            print(f"  ✅ 确保对话框在前台")
            
            # 获取任务数据
            task_type = self.resume_task_data.get('task_type')
            cid = self.resume_task_data.get('cid')
            uid = self.resume_task_data.get('uid')
            classid = self.resume_task_data.get('classid')
            unit_indices = self.resume_task_data.get('unit_indices', [])
            current_units = self.resume_task_data.get('current_units', [])
            completed_units = self.resume_task_data.get('completed_units', [])
            task_config = self.resume_task_data.get('task_config', {})
            
            logger.info(f"恢复任务数据 - 类型: {task_type}, 课程ID: {cid}, 用户ID: {uid}, 班级ID: {classid}")
            logger.info(f"单元数据 - 待处理: {unit_indices}, 已完成: {completed_units}, 当前单元数: {len(current_units)}")
            print(f"  ✅ 任务数据解析完成")
            
            # 查找对应的课程
            target_course = None
            
            # 🔧 修改：处理课程ID不匹配的情况
            print(f"\n[AccountDetail] resume_task - 开始恢复")
            print(f"恢复数据中的CID: {self.resume_task_data.get('cid')}")
            print(f"可用课程: {[c['cid'] for c in self.courses]}")
            
            # 方案1：精确匹配
            for course in self.courses:
                if str(course['cid']) == str(cid):
                    target_course = course
                    break
            
            # 方案2：如果找不到，使用第一门课程（临时方案）
            if not target_course:
                logger.warning(f"未找到课程ID为 {cid} 的课程，使用第一门课程")
                self.log(f"⚠️ 未找到课程ID {cid}，使用第一门课程")
                if self.courses:
                    target_course = self.courses[0]
                    cid = target_course['cid']  # 更新cid
                    self.log(f"✅ 使用课程: {target_course['name']} (CID: {cid})")
            
            if not target_course:
                logger.error(f"未找到对应课程，无法恢复任务")
                self.log(f"❌ 未找到对应的课程，无法恢复任务")
                from PyQt5.QtWidgets import QMessageBox
                msg = QMessageBox(QMessageBox.Warning, "错误", "未找到对应的课程，无法恢复任务")
                msg.setWindowFlags(msg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
                msg.exec_()
                return
            
            logger.info(f"找到目标课程: {target_course['name']}")
            
            # 设置当前课程
            self.current_course = target_course
            self.uid = uid
            self.classid = classid
            
            # 更新UI显示
            self.current_course_label.setText(target_course['name'])
            
            # 选中对应的课程项
            for i in range(self.courses_list.count()):
                item = self.courses_list.item(i)
                course = item.data(Qt.ItemDataRole.UserRole)
                if course and course['cid'] == cid:
                    self.courses_list.setCurrentItem(item)
                    break
            
            # 如果单元数据还没有加载，先加载单元数据
            if not self.current_units or len(self.current_units) != len(current_units):
                logger.info(f"单元数据未加载或数量不匹配，设置单元数据 - 当前: {len(self.current_units) if self.current_units else 0}, 需要: {len(current_units)}")
                # 设置单元数据
                self.current_units = current_units
                self.uid = uid
                self.classid = classid
                
                # 填充单元列表
                self.fill_unit_list_with_resume_data(unit_indices, completed_units)
                
                # 延迟恢复任务，确保UI更新完成
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, lambda: self.complete_task_resume(task_type, task_config, unit_indices))
            else:
                # 单元数据已加载，直接恢复任务
                logger.info(f"单元数据已加载，直接恢复任务")
                print(f"  ✅ 单元数据已加载，直接恢复任务")
                self.fill_unit_list_with_resume_data(unit_indices, completed_units)
                # 延迟恢复任务，确保UI更新完成
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(500, lambda: self.complete_task_resume(task_type, task_config, unit_indices))
                print(f"  ✅ 已安排500ms后完成任务恢复")
        except Exception as e:
            logger.error(f"恢复任务时发生错误: {str(e)}", exc_info=True)
            self.log(f"❌ 恢复任务失败: {str(e)}")
            print(f"  ❌ 恢复任务时发生错误: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[AccountDetail] resume_task 完成\n")
    
    def fill_unit_list_with_resume_data(self, unit_indices, completed_units):
        """使用恢复数据填充单元列表"""
        # 填充单元列表
        self.unit_list.clear()
        for i, unit in enumerate(self.current_units):
            unit_name = unit.get('name', f'单元 {i+1}')
            item = QListWidgetItem(f"单元 {i+1}: {unit_name}")
            
            # 如果单元已完成，则不选中
            if i in completed_units:
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setText(f"[已完成] 单元 {i+1}: {unit_name}")
            else:
                item.setCheckState(Qt.CheckState.Checked)
            
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.unit_list.addItem(item)
    
    def complete_task_resume(self, task_type, task_config, unit_indices):
        """完成任务恢复"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        try:
            # 确保UI元素已完全加载
            if not hasattr(self, 'mode_combo') or not self.mode_combo:
                logger.error("任务模式控件未初始化，无法恢复任务")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, lambda: self.complete_task_resume(task_type, task_config, unit_indices))
                return
            
            # 确保单元列表已加载
            if not hasattr(self, 'unit_list') or self.unit_list.count() == 0:
                logger.error("单元列表未加载，无法恢复任务")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, lambda: self.complete_task_resume(task_type, task_config, unit_indices))
                return
            
            # 设置任务模式
            if task_type == "刷作业":
                self.mode_combo.setCurrentText("刷作业")
                # 设置任务配置
                if 'accuracy_config' in task_config:
                    accuracy_config = task_config['accuracy_config']
                    if isinstance(accuracy_config, tuple):
                        # 正确率范围
                        self.accuracy_range_checkbox.setChecked(True)
                        self.accuracy_min_spin.setValue(accuracy_config[0])
                        self.accuracy_max_spin.setValue(accuracy_config[1])
                    else:
                        # 固定正确率
                        self.accuracy_range_checkbox.setChecked(False)
                        self.accuracy_spin.setValue(accuracy_config)
                if 'max_concurrent' in task_config:
                    self.homework_concurrent_spin.setValue(task_config['max_concurrent'])
            else:
                self.mode_combo.setCurrentText("刷时长")
                # 设置任务配置
                if 'total_minutes' in task_config:
                    time_value = task_config['total_minutes']
                    if time_value >= 60:
                        self.time_unit_combo.setCurrentText("小时")
                        self.time_spin.setValue(time_value // 60)
                    else:
                        self.time_unit_combo.setCurrentText("分钟")
                        self.time_spin.setValue(time_value)
                if 'random_range' in task_config:
                    self.time_random_spin.setValue(task_config['random_range'])
                if 'max_concurrent' in task_config:
                    self.concurrent_spin.setValue(task_config['max_concurrent'])
            
            # 生成任务ID
            task_id = self.progress_manager.generate_task_id(self.current_course['cid'], self.uid, task_type)
            
            # 立即开始任务，不延迟
            # 如果是从恢复任务开始的，立即删除旧的进度
            if self.resume_task_data:
                old_task_id = self.resume_task_data.get('task_id')
                if old_task_id:
                    success = self.progress_manager.clear_task_progress(old_task_id)
                    if success:
                        self.log(f"✅ 已删除旧的进度: {old_task_id}")
                        logger.info(f"已删除旧的进度: {old_task_id}")
                    else:
                        self.log(f"⚠️ 删除旧进度失败: {old_task_id}")
                        logger.error(f"删除旧进度失败: {old_task_id}")
            
            self.start_resumed_task(task_id)
            
            # 确保窗口被激活和置顶
            self.raise_()
            self.activateWindow()
            
            # 使用定时器再次确保窗口在前台
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(500, self._ensure_foreground_after_resume)
            
            logger.info(f"任务恢复准备完成 - 课程: {self.current_course['name']}, 任务类型: {task_type}")
            self.log(f"任务恢复准备完成，正在开始执行...")
            
            # 重置恢复任务标志
            self.need_resume_task = False
            logger.info(f"已重置恢复任务标志")
        except Exception as e:
            logger.error(f"完成任务恢复时发生错误: {str(e)}", exc_info=True)
            self.log(f"❌ 任务恢复失败: {str(e)}")
    
    def _ensure_foreground_after_resume(self):
        """确保任务恢复后对话框在前台"""
        try:
            self.raise_()
            self.activateWindow()
            from core.logger import get_logger
            logger = get_logger("AccountDetail")
            logger.info(f"已确保任务恢复后对话框在前台显示 - 账号: {self.account.username}")
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("AccountDetail")
            logger.error(f"确保任务恢复后对话框在前台显示时出错: {str(e)}")
    
    def start_resumed_task(self, task_id):
        """开始恢复的任务"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        try:
            # 确保所有必要的数据已加载
            if not self.current_course:
                logger.error("没有选择课程，无法开始任务")
                return
            
            # 确保单元列表已加载
            if not hasattr(self, 'unit_list') or self.unit_list.count() == 0:
                logger.error("单元列表未加载，无法开始任务")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, lambda: self.start_resumed_task(task_id))
                return
            
            # 获取选中的单元
            units_to_process = []
            for i in range(self.unit_list.count()):
                item = self.unit_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    unit_index = item.data(Qt.ItemDataRole.UserRole)
                    units_to_process.append(unit_index)
            
            if not units_to_process:
                logger.warning("没有选中的单元，无法开始任务")
                return
            
            # 确保UI控件已初始化
            if not hasattr(self, 'mode_combo') or not self.mode_combo:
                logger.error("任务模式控件未初始化，无法开始任务")
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(1000, lambda: self.start_resumed_task(task_id))
                return
            
            mode = self.mode_combo.currentText()
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不确定进度
            
            if mode == "刷作业":
                # 根据复选框状态决定正确率配置
                if self.accuracy_range_checkbox.isChecked():
                    # 使用正确率范围
                    accuracy_config = (self.accuracy_min_spin.value(), self.accuracy_max_spin.value())
                else:
                    # 使用固定正确率
                    accuracy_config = self.accuracy_spin.value()
                
                homework_concurrent = self.homework_concurrent_spin.value()
                
                self.log(f"恢复刷作业任务 (已选 {len(units_to_process)} 个单元, {homework_concurrent} 并发)...")
                self.update_status("运行中")
                
                self.study_thread = StudyThread(
                    self.client,
                    self.current_course['cid'],
                    self.uid,
                    self.classid,
                    units_to_process,
                    accuracy_config,
                    self.current_units,
                    max_concurrent=homework_concurrent,
                    username=self.account.username,
                    task_id=task_id
                )
                
                # 连接信号
                self.study_thread.progress_update.connect(self.handle_progress_update)
                self.study_thread.study_finished.connect(self.on_study_finished)
                
                # 保存任务进度
                self.save_task_progress(task_id, "刷作业", units_to_process, {
                    'accuracy_config': accuracy_config,
                    'max_concurrent': homework_concurrent
                })
                
                # 启动线程
                self.study_thread.start()
                logger.info(f"刷作业线程已启动 - 任务ID: {task_id}")
            else:
                # 获取时间值和单位
                time_value = self.time_spin.value()
                time_unit = self.time_unit_combo.currentText()
                
                # 转换为分钟
                if time_unit == "小时":
                    total_minutes = time_value * 60
                else:
                    total_minutes = time_value
                    
                random_range = self.time_random_spin.value()
                concurrent = self.concurrent_spin.value()
                
                self.log(f"恢复刷时长任务 (已选 {len(units_to_process)} 个单元, 每单元 {time_value} {time_unit}, {concurrent} 并发)...")
                self.update_status("运行中")
                
                self.study_thread = TimeStudyThread(
                    self.client,
                    self.current_course['cid'],
                    self.uid,
                    self.classid,
                    units_to_process,
                    total_minutes,
                    random_range,
                    self.current_units,
                    max_concurrent=concurrent,
                    username=self.account.username,
                    task_id=task_id
                )
                
                # 连接信号
                self.study_thread.progress_update.connect(self.handle_progress_update)
                self.study_thread.study_finished.connect(self.on_study_finished)
                
                # 保存任务进度
                self.save_task_progress(task_id, "刷时长", units_to_process, {
                    'total_minutes': total_minutes,
                    'random_range': random_range,
                    'max_concurrent': concurrent
                })
                
                # 启动线程
                self.study_thread.start()
                logger.info(f"刷时长线程已启动 - 任务ID: {task_id}")
            
            logger.info(f"恢复任务已开始 - 账号: {self.account.username}, 课程: {self.current_course['name']}, 任务类型: {mode}")
        except Exception as e:
            logger.error(f"开始恢复任务时发生错误: {str(e)}", exc_info=True)
            self.log(f"❌ 开始恢复任务失败: {str(e)}")
            # 重置按钮状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
        self.log(f"任务已恢复并开始执行")
    
    def save_task_progress(self, task_id, task_type, unit_indices, task_config):
        """保存任务进度
        
        Args:
            task_id: 任务ID
            task_type: 任务类型（刷作业/刷时长）
            unit_indices: 选中单元的索引列表
            task_config: 任务配置字典
        """
        from core.logger import get_logger
        logger = get_logger("AccountDetail")
        
        # 获取当前时间
        import time
        current_time = time.time()
        
        # 保存任务进度
        success = self.progress_manager.save_task_progress(
            task_id=task_id,
            task_type=task_type,
            cid=self.current_course['cid'],
            uid=self.uid,
            classid=self.classid,
            unit_indices=unit_indices,
            current_units=self.current_units,
            completed_units=[],  # 初始时没有完成的单元
            completed_courses={0: []},  # 初始时没有完成的课程
            task_config=task_config,
            username=self.account.username  # 传递username
        )
        
        if success:
            logger.info(f"任务进度已保存 - 任务ID: {task_id}, 类型: {task_type}")
        else:
            logger.error(f"任务进度保存失败 - 任务ID: {task_id}")
        
        return success

    # ========== 学习统计相关 ==========
    
    def get_user_id(self):
        """获取用户ID"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        if not self.is_logged_in:
            logger.warning("未登录，无法获取用户ID")
            return

        if self.uid:
            logger.info(f"用户ID已存在: {self.uid}")
            return

        logger.info(f"开始获取用户ID - 账号: {self.account.username}")
        self.log("正在获取用户ID...")

        try:
            success, uid, message = self.client.get_user_id()
            if success:
                self.uid = uid
                self.log(f"✅ 用户ID: {uid}")
                logger.info(f"获取用户ID成功 - {uid}")

                # 更新UI显示
                if hasattr(self, 'user_id_label'):
                    self.user_id_label.setText(f"用户ID: {uid}")
            else:
                self.log(f"❌ 获取用户ID失败: {message}")
                logger.error(f"获取用户ID失败 - {message}")
        except Exception as e:
            self.log(f"❌ 获取用户ID异常: {str(e)}")
            logger.error(f"获取用户ID异常: {str(e)}")

    def fetch_user_study_stats(self):
        """获取用户总体学习统计"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        if not self.is_logged_in:
            logger.warning("未登录，无法获取学习统计")
            return

        if not self.uid:
            logger.warning("未获取到用户ID，先获取用户ID")
            self.get_user_id()
            # 延迟一下再获取统计
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(500, self.fetch_user_study_stats)
            return

        logger.info(f"开始获取学习统计 - 账号: {self.account.username}, UID: {self.uid}")
        self.log("正在获取学习统计...")

        # 创建获取学习统计的线程
        self.stats_thread = workers.UserStatsThread(self.client)
        self.stats_thread.stats_result.connect(self.on_stats_result)
        self.stats_thread.status_updated.connect(self.update_status)
        self.stats_thread.log_message.connect(self.log)
        self.stats_thread.start()

    def on_stats_result(self, success: bool, stats_data: dict, message: str):
        """学习统计结果回调"""
        from core.logger import get_logger
        logger = get_logger("AccountDetail")

        if success:
            # 提取关键信息（根据实际API返回结构调整）
            total_time = stats_data.get('totalStudyTime') or stats_data.get('total_time')
            today_time = stats_data.get('todayStudyTime') or stats_data.get('today_time')

            # 更新UI显示
            if hasattr(self, 'total_time_label') and total_time:
                self.total_time_label.setText(f"累计学习: {total_time}")

            if hasattr(self, 'today_time_label') and today_time:
                self.today_time_label.setText(f"今日学习: {today_time}")

            self.log(f"✅ 学习统计 - 累计: {total_time}, 今日: {today_time}")
            logger.info(f"获取学习统计成功 - 累计: {total_time}, 今日: {today_time}")
        else:
            self.log(f"❌ 获取学习统计失败: {message}")
            logger.error(f"获取学习统计失败: {message}")


