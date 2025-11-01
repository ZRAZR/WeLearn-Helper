import sys
import requests
import re
import base64
import random
import time
from typing import List, Tuple, Union, Dict, Any
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, 
                             QProgressBar, QListWidget, QListWidgetItem, QMessageBox,
                             QGroupBox, QSpinBox, QSplitter, QTabWidget, QFrame, QDialog,
                             QDialogButtonBox, QGridLayout)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor
import webbrowser


class TimeDialog(QDialog):
    """时长设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Qt")
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        input_layout = QGridLayout()
        
        input_layout.addWidget(QLabel("最小时长:"), 0, 0)
        self.min_time = QSpinBox()
        self.min_time.setRange(1, 3600)
        self.min_time.setValue(10)
        self.min_time.setSuffix("秒")
        input_layout.addWidget(self.min_time, 0, 1)
        
        input_layout.addWidget(QLabel("最大时长:"), 1, 0)
        self.max_time = QSpinBox()
        self.max_time.setRange(1, 3600)
        self.max_time.setValue(30)
        self.max_time.setSuffix("秒")
        input_layout.addWidget(self.max_time, 1, 1)
        
        layout.addLayout(input_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return self.min_time.value(), self.max_time.value()

class AccuracyDialog(QDialog):
    """正确率设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Qt")
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        input_layout = QGridLayout()
        
        input_layout.addWidget(QLabel("最小正确率:"), 0, 0)
        self.min_accuracy = QSpinBox()
        self.min_accuracy.setRange(0, 100)
        self.min_accuracy.setValue(70)
        self.min_accuracy.setSuffix("%")
        input_layout.addWidget(self.min_accuracy, 0, 1)
        
        input_layout.addWidget(QLabel("最大正确率:"), 1, 0)
        self.max_accuracy = QSpinBox()
        self.max_accuracy.setRange(0, 100)
        self.max_accuracy.setValue(100)
        self.max_accuracy.setSuffix("%")
        input_layout.addWidget(self.max_accuracy, 1, 1)
        
        layout.addLayout(input_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return self.min_accuracy.value(), self.max_accuracy.value()

class UnitsThread(QThread):
    """获取单元线程"""
    units_result = pyqtSignal(bool, list, str)
    
    def __init__(self, session, cid):
        super().__init__()
        self.session = session
        self.cid = cid

    def run(self):
        try:
            url = f"https://welearn.sflep.com/student/course_info.aspx?cid={self.cid}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                self.units_result.emit(False, [], f"获取课程信息失败，状态码: {response.status_code}")
                return
            
            uid_match = re.search(r'"uid":\s*(\d+),', response.text)
            classid_match = re.search(r'"classid":"(\w+)"', response.text)
            
            if not uid_match or not classid_match:
                self.units_result.emit(False, [], "无法解析课程信息")
                return
                
            uid = uid_match.group(1)
            classid = classid_match.group(1)

            url = 'https://welearn.sflep.com/ajax/StudyStat.aspx'
            response = self.session.get(
                url, 
                params={'action': 'courseunits', 'cid': self.cid, 'uid': uid},
                headers={'Referer': 'https://welearn.sflep.com/2019/student/course_info.aspx'},
                timeout=10
            )
            
            if response.status_code != 200:
                self.units_result.emit(False, [], f"获取单元信息失败，状态码: {response.status_code}")
                return
                
            data = response.json()
            if 'info' not in data:
                self.units_result.emit(False, [], "单元信息格式错误")
                return
            
            result_data = {
                'uid': uid,
                'classid': classid,
                'units': data['info']
            }
            self.units_result.emit(True, [result_data], "获取单元信息成功")
            
        except Exception as e:
            self.units_result.emit(False, [], f"获取课程单元失败: {str(e)}")

class LoginThread(QThread):
    """登录线程"""
    login_result = pyqtSignal(bool, str)
    
    def __init__(self, username, password, session):
        super().__init__()
        self.username = username
        self.password = password
        self.session = session

    def to_hex_byte_array(self, byte_array: bytes) -> str:
        return ''.join([f'{byte:02x}' for byte in byte_array])

    def generate_cipher_text(self, password: str) -> List[str]:
        T0 = int(round(time.time() * 1000))
        P = password.encode('utf-8')
        V = (T0 >> 16) & 0xFF
        
        for byte in P:
            V ^= byte
            
        remainder = V % 100
        T1 = int((T0 // 100) * 100 + remainder)
        P1 = self.to_hex_byte_array(P)
        S = f"{T1}*" + P1
        S_encoded = S.encode('utf-8')
        E = base64.b64encode(S_encoded).decode('utf-8')
        
        return [E, str(T1)]

    def run(self):
        try:
            response = self.session.get(
                "https://welearn.sflep.com/user/prelogin.aspx?loginret=http://welearn.sflep.com/user/loginredirect.aspx",
                timeout=10
            )
            
            if response.status_code != 200:
                self.login_result.emit(False, f"网络请求失败，状态码: {response.status_code}")
                return
            
            url_parts = response.url.split("%26")
            if len(url_parts) < 7:
                self.login_result.emit(False, "登录URL格式异常")
                return
            
            code_challenge = url_parts[4].split("%3D")[1] if len(url_parts[4].split("%3D")) > 1 else ""
            state = url_parts[6].split("%3D")[1] if len(url_parts[6].split("%3D")) > 1 else ""
            
            rturl = (f"/connect/authorize/callback?client_id=welearn_web&redirect_uri=https%3A%2F%2Fwelearn.sflep.com%2Fsignin-sflep"
                    f"&response_type=code&scope=openid%20profile%20email%20phone%20address&code_challenge={code_challenge}"
                    f"&code_challenge_method=S256&state={state}&x-client-SKU=ID_NET472&x-client-ver=6.32.1.0")
            
            enpwd = self.generate_cipher_text(self.password)
            
            form_data = {
                "rturl": rturl,
                "account": self.username,
                "pwd": enpwd[0],
                "ts": enpwd[1]
            }

            response = self.session.post(
                "https://sso.sflep.com/idsvr/account/login", 
                data=form_data,
                timeout=10
            )
            
            if response.status_code != 200:
                self.login_result.emit(False, f"登录请求失败，状态码: {response.status_code}")
                return
            
            result = response.json()
            code = result.get("code", -1)

            if code == 1:
                self.login_result.emit(False, "帐号或密码错误")
                return

            self.session.get(
                "https://welearn.sflep.com/user/prelogin.aspx?loginret=http://welearn.sflep.com/user/loginredirect.aspx",
                timeout=10
            )

            if code == 0:
                self.login_result.emit(True, "登录成功")
            else:
                self.login_result.emit(False, "登录失败")
                
        except Exception as e:
            self.login_result.emit(False, f"登录过程中发生错误: {str(e)}")

class CourseThread(QThread):
    """获取课程线程"""
    course_result = pyqtSignal(bool, list, str)
    
    def __init__(self, session):
        super().__init__()
        self.session = session

    def run(self):
        try:
            url = "https://welearn.sflep.com/ajax/authCourse.aspx?action=gmc"
            response = self.session.get(
                url, 
                headers={"Referer": "https://welearn.sflep.com/2019/student/index.aspx"},
                timeout=10
            )
            
            if response.status_code != 200:
                self.course_result.emit(False, [], f"获取课程失败，状态码: {response.status_code}")
                return
            
            data = response.json()
            if not data.get("clist"):
                self.course_result.emit(False, [], "没有找到课程")
                return
                
            self.course_result.emit(True, data["clist"], "获取课程成功")
            
        except Exception as e:
            self.course_result.emit(False, [], f"获取课程列表失败: {str(e)}")

class StudyThread(QThread):
    """学习线程"""
    progress_update = pyqtSignal(str, str)
    study_finished = pyqtSignal(dict)
    
    def __init__(self, session, cid, uid, classid, unit_idx, accuracy_config, current_units):
        super().__init__()
        self.session = session
        self.cid = cid
        self.uid = uid
        self.classid = classid
        self.unit_idx = unit_idx
        self.accuracy_config = accuracy_config
        self.current_units = current_units
        self.total_way1_succeed, self.total_way1_failed = 0, 0
        self.total_way2_succeed, self.total_way2_failed = 0, 0


    def _submit_course_progress(self, scoid: str, accuracy: str):
        way1_succeed, way1_failed, way2_succeed, way2_failed = 0, 0, 0, 0
        ajax_url = "https://welearn.sflep.com/Ajax/SCO.aspx"
        
        try:
            data = ('{"cmi":{"completion_status":"completed","interactions":[],"launch_data":"","progress_measure":"1",'
                   f'"score":{{"scaled":"{accuracy}","raw":"100"}},"session_time":"0","success_status":"unknown",'
                   '"total_time":"0","mode":"normal"},"adl":{"data":[]},"cci":{"data":[],"service":{"dictionary":'
                   '{"headword":"","short_cuts":""},"new_words":[],"notes":[],"writing_marking":[],"record":'
                   '{"files":[]},"play":{"offline_media_id":"9999"}},"retry_count":"0","submit_time":""}}[INTERACTIONINFO]')

            self.session.post(
                ajax_url, 
                data={
                    "action": "startsco160928",
                    "cid": self.cid,
                    "scoid": scoid,
                    "uid": self.uid
                },
                headers={
                    "Referer": f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={self.cid}&classid={self.classid}&sco={scoid}"
                },
                timeout=10
            )
            
            response = self.session.post(
                ajax_url, 
                data={
                    "action": "setscoinfo",
                    "cid": self.cid,
                    "scoid": scoid,
                    "uid": self.uid,
                    "data": data,
                    "isend": "False"
                },
                headers={
                    "Referer": f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={self.cid}&classid={self.classid}&sco={scoid}"
                },
                timeout=10
            )
            
            if response.status_code == 200 and '"ret":0' in response.text:
                way1_succeed = 1
            else:
                way1_failed = 1

            response = self.session.post(
                ajax_url, 
                data={
                    "action": "savescoinfo160928",
                    "cid": self.cid,
                    "scoid": scoid,
                    "uid": self.uid,
                    "progress": "100",
                    "crate": accuracy,
                    "status": "unknown",
                    "cstatus": "completed",
                    "trycount": "0",
                },
                headers={
                    "Referer": f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={self.cid}&classid={self.classid}&sco={scoid}"
                },
                timeout=10
            )
            
            if response.status_code == 200 and '"ret":0' in response.text:
                way2_succeed = 1
            else:
                way2_failed = 1
                
        except Exception:
            way1_failed = 1
            way2_failed = 1
            
        return way1_succeed, way1_failed, way2_succeed, way2_failed

    def process_unit(self, unit_index):
        way1_succeed, way1_failed, way2_succeed, way2_failed = 0, 0, 0, 0
        
        try:
            url = 'https://welearn.sflep.com/ajax/StudyStat.aspx'
            params = {
                'action': 'scoLeaves', 
                'cid': self.cid, 
                'uid': self.uid, 
                'unitidx': unit_index, 
                'classid': self.classid
            }
            
            headers = {
                "Referer": f"https://welearn.sflep.com/2019/student/course_info.aspx?cid={self.cid}",
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            data = response.json()

            for course in data["info"]:
                course_location = course.get("location", "未知课程")
                    
                if course.get('isvisible') == 'false':
                    self.progress_update.emit("skip", f"[跳过] {course_location}")
                    continue
                        
                if "未" in course.get("iscomplete", ""):
                    self.progress_update.emit("start", f"[进行] {course_location}")
                        
                    if isinstance(self.accuracy_config, tuple):
                        accuracy = str(random.randint(self.accuracy_config[0], self.accuracy_config[1]))
                    else:
                        accuracy = str(self.accuracy_config)
                        
                    result = self._submit_course_progress(course["id"], accuracy)
                    way1_succeed += result[0]
                    way1_failed += result[1]
                    way2_succeed += result[2]
                    way2_failed += result[3]
                    
                    status_msg = f"[完成] {course_location} - 正确率: {accuracy}%"
                    if result[0] == 1:
                        status_msg += " (步骤1:成功)"
                    else:
                        status_msg += " (步骤1:失败)"
                    if result[2] == 1:
                        status_msg += " (步骤2:成功)"
                    else:
                        status_msg += " (步骤2:失败)"
                        
                    self.progress_update.emit("finish", status_msg)
                else:
                    self.progress_update.emit("completed", f"[已完成] {course_location}")
                
        except Exception as e:
            self.progress_update.emit("error", f"处理单元 {unit_index + 1} 时发生错误: {str(e)}")
        
        return way1_succeed, way1_failed, way2_succeed, way2_failed

    def run(self):
        total_way1_succeed, total_way1_failed = 0, 0
        total_way2_succeed, total_way2_failed = 0, 0
        
        try:
            if self.unit_idx == -1:
                for unit_index in range(len(self.current_units)):
                    self.progress_update.emit("unit_start", f"\n=== 开始处理第 {unit_index + 1} 单元 ===")
                    result = self.process_unit(unit_index)
                    total_way1_succeed += result[0]
                    total_way1_failed += result[1]
                    total_way2_succeed += result[2]
                    total_way2_failed += result[3]
                    current_stats = {
                        'way1_succeed': total_way1_succeed,
                        'way1_failed': total_way1_failed,
                        'way2_succeed': total_way2_succeed,
                        'way2_failed': total_way2_failed
                    }
                    self.study_finished.emit(current_stats)
                    self.progress_update.emit("unit_finish", f"=== 第 {unit_index + 1} 单元处理完成 ===\n")
            else:
                result = self.process_unit(self.unit_idx)
                total_way1_succeed, total_way1_failed, total_way2_succeed, total_way2_failed = result
            
            result = {
                'way1_succeed': total_way1_succeed,
                'way1_failed': total_way1_failed,
                'way2_succeed': total_way2_succeed,
                'way2_failed': total_way2_failed
            }
            self.study_finished.emit(result)
                
        except Exception as e:
            self.progress_update.emit("error", f"学习过程中发生错误: {str(e)}")

class TimeStudyThread(QThread):
    """刷时长线程"""
    progress_update = pyqtSignal(str, str)
    study_finished = pyqtSignal(dict)
    
    def __init__(self, session, cid, uid, classid, unit_idx, time_config, current_units):
        super().__init__()
        self.session = session
        self.cid = cid
        self.uid = uid
        self.classid = classid
        self.unit_idx = unit_idx
        self.time_config = time_config
        self.current_units = current_units

    def generate_learning_time(self):
        if isinstance(self.time_config, tuple):
            return random.randint(self.time_config[0], self.time_config[1])
        else:
            return self.time_config

    def simulate_learning(self, learning_time, chapter):
        try:
            scoid = chapter['id']
            common_data = {
                'uid': self.uid,
                'cid': self.cid,
                'scoid': scoid
            }
            
            common_headers = {
                'Referer': 'https://welearn.sflep.com/student/StudyCourse.aspx'
            }
            
            response = self.session.post(
                "https://welearn.sflep.com/Ajax/SCO.aspx",
                data={**common_data, 'action': 'startsco160928'},
                headers=common_headers
            )
            
            for current_time in range(1, learning_time + 1):
                time.sleep(1)
                if current_time % 60 == 0:
                    self.session.post(
                        "https://welearn.sflep.com/Ajax/SCO.aspx",
                        data={**common_data, 'action': 'keepsco_with_getticket_with_updatecmitime'},
                        headers=common_headers
                    )
            
            self.session.post(
                "https://welearn.sflep.com/Ajax/SCO.aspx",
                data={**common_data, 'action': 'savescoinfo160928'},
                headers=common_headers
            )
            
            return True
        except Exception as e:
            return False

    def process_unit(self, unit_index):
        success_count, fail_count = 0, 0
        
        try:
            response = self.session.get(
                f"https://welearn.sflep.com/ajax/StudyStat.aspx?action=scoLeaves&cid={self.cid}&uid={self.uid}&unitidx={unit_index}&classid={self.classid}",
                headers={'Referer': f'https://welearn.sflep.com/2019/student/course_info.aspx?cid={self.cid}'}
            )
            
            data = response.json()
            for chapter in data["info"]:
                course_location = chapter.get("location", "未知课程")
                
                if chapter.get('isvisible') == 'false':
                    self.progress_update.emit("skip", f"[跳过] {course_location}")
                    continue
                
                learning_time = self.generate_learning_time()
                self.progress_update.emit("start", f"[刷时长] {course_location} - 时长: {learning_time}秒")
                
                if self.simulate_learning(learning_time, chapter):
                    success_count += 1
                    self.progress_update.emit("finish", f"[完成] {course_location} - 时长: {learning_time}秒")
                else:
                    fail_count += 1
                    self.progress_update.emit("error", f"[失败] {course_location}")
                    
        except Exception as e:
            self.progress_update.emit("error", f"处理单元 {unit_index + 1} 时发生错误: {str(e)}")
        
        return success_count, fail_count

    def run(self):
        total_success, total_fail = 0, 0
        
        try:
            if self.unit_idx == -1:
                for unit_index in range(len(self.current_units)):
                    self.progress_update.emit("unit_start", f"\n=== 开始处理第 {unit_index + 1} 单元 ===")
                    success, fail = self.process_unit(unit_index)
                    total_success += success
                    total_fail += fail
                    self.progress_update.emit("unit_finish", f"=== 第 {unit_index + 1} 单元处理完成 ===\n")
            else:
                success, fail = self.process_unit(self.unit_idx)
                total_success, total_fail = success, fail
            
            result = {
                'way1_succeed': total_success,
                'way1_failed': total_fail,
                'way2_succeed': total_success,
                'way2_failed': total_fail
            }
            self.study_finished.emit(result)
            
        except Exception as e:
            self.progress_update.emit("error", f"刷时长过程中发生错误: {str(e)}")



class WeLearnUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.courses = []
        self.current_course = None
        self.current_units = []
        self.uid = ""
        self.classid = ""
        self.study_thread = None
        self.time_thread = None
        self.init_ui()

    def closeEvent(self, event):
        if self.study_thread and self.study_thread.isRunning():
            self.study_thread.quit()
            self.study_thread.wait(3000)
            if self.study_thread.isRunning():
                self.study_thread.terminate()
        if self.time_thread and self.time_thread.isRunning():
            self.time_thread.quit()
            self.time_thread.wait(3000)
            if self.time_thread.isRunning():
                self.time_thread.terminate()
        event.accept()

    def init_ui(self):
        self.setWindowTitle("WeLearn 自动学习工具")
        self.setGeometry(100, 100, 1000, 700)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
            }
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        login_tab = QWidget()
        self.setup_login_tab(login_tab)
        self.tab_widget.addTab(login_tab, "登录")
        
        study_setup_tab = QWidget()
        self.setup_study_tab(study_setup_tab)
        self.tab_widget.addTab(study_setup_tab, "设置")
        
        status_tab = QWidget()
        self.setup_status_tab(status_tab)
        self.tab_widget.addTab(status_tab, "日志")

    def setup_login_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        login_group = QGroupBox("登录信息")
        login_layout = QVBoxLayout(login_group)
        
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("用户名:"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        user_layout.addWidget(self.username_input)
        login_layout.addLayout(user_layout)
        
        pwd_layout = QHBoxLayout()
        pwd_layout.addWidget(QLabel("密码:"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        pwd_layout.addWidget(self.password_input)
        login_layout.addLayout(pwd_layout)
        
        self.login_btn = QPushButton("登录")
        self.login_btn.clicked.connect(self.do_login)
        login_layout.addWidget(self.login_btn)
        
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("""
        GitHub: jhl337
        本人是一位来自黑大的苦逼学生，因不满校内各种付费代刷课，所以制作了这款软件
        
        软件仅供学习参考使用，永久免费禁止倒卖
        禁止使用软件进行任何代刷牟利，以此造成的任何问题本人不负责任

        后续可能还会推出一些自动刷知到等课程的软件，敬请期待
        有任何问题欢迎提交issue多多交流
        
        部分课程可能会遇到步骤1/2其中一个执行失败
        多数情况下有一个成功就可以正常积分
        积分情况参阅Welearn官网: welearn.sflep.com
        """))
        login_layout.addLayout(info_layout)
        
        self.open_browser_btn = QPushButton("点此打开本项目 Repo")
        self.open_browser_btn.clicked.connect(self.do_open_browser)
        self.open_browser2_btn = QPushButton("点此打开 WeLearn 官网")
        self.open_browser2_btn.clicked.connect(self.do_open_browser2)
        login_layout.addWidget(self.open_browser_btn)

        login_layout.addWidget(self.open_browser2_btn)
        
        
        layout.addWidget(login_group)
        layout.addStretch()

    def setup_study_tab(self, parent):
        """合并的课程选择和学习设置标签页"""
        layout = QVBoxLayout(parent)
        
        course_group = QGroupBox("课程选择")
        course_layout = QVBoxLayout(course_group)
        
        self.refresh_courses_btn = QPushButton("刷新课程列表")
        self.refresh_courses_btn.clicked.connect(self.refresh_courses)
        self.refresh_courses_btn.setEnabled(False)
        course_layout.addWidget(self.refresh_courses_btn)
        
        self.courses_list = QListWidget()
        course_layout.addWidget(self.courses_list)
        
        self.select_course_btn = QPushButton("选择课程")
        self.select_course_btn.clicked.connect(self.select_course)
        self.select_course_btn.setEnabled(False)
        course_layout.addWidget(self.select_course_btn)
        
        layout.addWidget(course_group)
        
        layout.addSpacing(10)
        
        study_group = QGroupBox("学习设置")
        study_layout = QVBoxLayout(study_group)
        
        current_course_layout = QHBoxLayout()
        current_course_layout.addWidget(QLabel("当前课程:"))
        self.current_course_label = QLabel("未选择")
        self.current_course_label.setStyleSheet("color: #666; font-style: italic;")
        current_course_layout.addWidget(self.current_course_label)
        current_course_layout.addStretch()
        study_layout.addLayout(current_course_layout)
        
        # 新增：模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("学习模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["刷作业模式", "刷时长模式"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        study_layout.addLayout(mode_layout)
        
        unit_layout = QHBoxLayout()
        unit_layout.addWidget(QLabel("单元选择:"))
        self.unit_combo = QComboBox()
        self.unit_combo.setEnabled(False)
        unit_layout.addWidget(self.unit_combo)
        study_layout.addLayout(unit_layout)
        
        # 刷作业模式的设置容器
        self.homework_widget = QWidget()
        homework_layout = QHBoxLayout(self.homework_widget)
        homework_layout.addWidget(QLabel("正确率设置:"))
        
        self.accuracy_mode_combo = QComboBox()
        self.accuracy_mode_combo.addItems(["固定正确率", "随机正确率"])
        self.accuracy_mode_combo.currentTextChanged.connect(self.on_accuracy_mode_changed)
        homework_layout.addWidget(self.accuracy_mode_combo)
        
        self.fixed_accuracy_spin = QSpinBox()
        self.fixed_accuracy_spin.setRange(0, 100)
        self.fixed_accuracy_spin.setValue(100)
        self.fixed_accuracy_spin.setSuffix("%")
        homework_layout.addWidget(self.fixed_accuracy_spin)
        
        self.random_accuracy_btn = QPushButton("设置随机范围")
        self.random_accuracy_btn.clicked.connect(self.set_random_accuracy)
        homework_layout.addWidget(self.random_accuracy_btn)
        self.random_accuracy_btn.hide()
        
        self.random_accuracy_label = QLabel("70%-100%")
        homework_layout.addWidget(self.random_accuracy_label)
        self.random_accuracy_label.hide()
        
        study_layout.addWidget(self.homework_widget)
        
        # 刷时长模式的设置容器
        self.time_widget = QWidget()
        time_layout = QVBoxLayout(self.time_widget)

        time_input_layout = QHBoxLayout()
        time_input_layout.addWidget(QLabel("时长设置:"))

        self.time_mode_combo = QComboBox()
        self.time_mode_combo.addItems(["固定时长", "随机时长"])
        self.time_mode_combo.currentTextChanged.connect(self.on_time_mode_changed)
        time_input_layout.addWidget(self.time_mode_combo)

        self.fixed_time_spin = QSpinBox()
        self.fixed_time_spin.setRange(1, 3600)
        self.fixed_time_spin.setValue(30)
        self.fixed_time_spin.setSuffix("秒")
        time_input_layout.addWidget(self.fixed_time_spin)

        self.random_time_btn = QPushButton("设置随机范围")
        self.random_time_btn.clicked.connect(self.set_random_time)
        time_input_layout.addWidget(self.random_time_btn)
        self.random_time_btn.hide()

        self.random_time_label = QLabel("10-30秒")
        time_input_layout.addWidget(self.random_time_label)
        self.random_time_label.hide()

        time_layout.addLayout(time_input_layout)

        time_help_label = QLabel("每个练习增加指定学习时长，建议设置10-60秒")
        time_help_label.setStyleSheet("color: #666; font-size: 12px;")
        time_layout.addWidget(time_help_label)

        study_layout.addWidget(self.time_widget)
        self.time_widget.hide()
        
        self.start_study_btn = QPushButton("开始学习")
        self.start_study_btn.clicked.connect(self.start_study)
        self.start_study_btn.setEnabled(False)
        study_layout.addWidget(self.start_study_btn)
        
        layout.addWidget(study_group)
        layout.addStretch()

    def set_random_time(self, checked=False):
        """打开随机时长设置对话框"""
        dialog = TimeDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        if dialog.exec_() == QDialog.Accepted:
            min_val, max_val = dialog.get_values()
            self.random_time_label.setText(f"{min_val}-{max_val}秒")

    def on_time_mode_changed(self, mode):
        """处理时长模式切换"""
        if mode == "固定时长":
            self.fixed_time_spin.show()
            self.random_time_btn.hide()
            self.random_time_label.hide()
        else:
            self.fixed_time_spin.hide()
            self.random_time_btn.show()
            # self.random_time_label.show()

    def on_mode_changed(self, mode):
        if mode == "刷作业模式":
            self.homework_widget.show()
            self.time_widget.hide()
            self.start_study_btn.setText("开始学习")
        else:
            self.homework_widget.hide()
            self.time_widget.show()
            self.start_study_btn.setText("开始刷时长")

    def on_accuracy_mode_changed(self, mode):
        if mode == "固定正确率":
            self.fixed_accuracy_spin.show()
            self.random_accuracy_btn.hide()
            self.random_accuracy_label.hide()
        else:
            self.fixed_accuracy_spin.hide()
            self.random_accuracy_btn.show()
            # self.random_accuracy_label.show()

    def setup_status_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        progress_group = QGroupBox("程序输出")
        progress_layout = QVBoxLayout(progress_group)
    
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)

        self.progress_text.setLineWrapMode(QTextEdit.NoWrap)
        # self.progress_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # self.progress_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        progress_layout.addWidget(self.progress_text)
        
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("步骤1成功:"))
        self.way1_success_label = QLabel("0")
        stats_layout.addWidget(self.way1_success_label)
        
        stats_layout.addWidget(QLabel("步骤1失败:"))
        self.way1_fail_label = QLabel("0")
        stats_layout.addWidget(self.way1_fail_label)
        
        stats_layout.addWidget(QLabel("步骤2成功:"))
        self.way2_success_label = QLabel("0")
        stats_layout.addWidget(self.way2_success_label)
        
        stats_layout.addWidget(QLabel("步骤2失败:"))
        self.way2_fail_label = QLabel("0")
        stats_layout.addWidget(self.way2_fail_label)
        
        progress_layout.addLayout(stats_layout)
        
        layout.addWidget(progress_group)

    def set_random_accuracy(self, checked=False):
        """打开随机正确率设置对话框"""
        dialog = AccuracyDialog(self)
        dialog.setWindowFlags (dialog.windowFlags () & ~Qt.WindowContextHelpButtonHint)
        if dialog.exec_() == QDialog.Accepted:
            min_val, max_val = dialog.get_values()
            self.random_accuracy_label.setText(f"{min_val}%-{max_val}%")

    def do_open_browser(self, checked=False):
        webbrowser.open("https://github.com/jhl337/Auto_WeLearn/")

    def do_open_browser2(self, checked=False):
        webbrowser.open("http://welearn.sflep.com")

    def do_login(self, checked=False):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        
        self.login_thread = LoginThread(username, password, self.session)
        self.login_thread.login_result.connect(self.on_login_result)
        self.login_thread.start()

    def on_login_result(self, success, message):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("登录")
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.refresh_courses_btn.setEnabled(True)
        else:
            QMessageBox.warning(self, "失败", message)

    def refresh_courses(self, checked=False):
        self.refresh_courses_btn.setEnabled(False)
        self.refresh_courses_btn.setText("获取中...")
        
        self.course_thread = CourseThread(self.session)
        self.course_thread.course_result.connect(self.on_courses_result)
        self.course_thread.start()

    def on_courses_result(self, success, courses, message):
        self.refresh_courses_btn.setEnabled(True)
        self.refresh_courses_btn.setText("刷新课程列表")
        
        if success:
            self.courses = courses
            self.courses_list.clear()
            for course in courses:
                item = QListWidgetItem(f"{course['name']} (完成度: {course['per']}%)")
                item.setData(Qt.UserRole, course)
                self.courses_list.addItem(item)
            self.select_course_btn.setEnabled(True)
            QMessageBox.information(self, "成功", f"获取到 {len(courses)} 门课程")
        else:
            QMessageBox.warning(self, "失败", message)

    def select_course(self, checked=False):
        current_item = self.courses_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请选择一门课程")
            return
        
        self.current_course = current_item.data(Qt.UserRole)
        self.current_course_label.setText(self.current_course['name'])
        
        self.get_course_units()

    def get_course_units(self):
        """获取课程的单元信息"""
        self.unit_combo.setEnabled(False)
        self.start_study_btn.setEnabled(False)
        
        self.units_thread = UnitsThread(self.session, self.current_course['cid'])
        self.units_thread.units_result.connect(self.on_units_result)
        self.units_thread.start()
        
        QMessageBox.information(self, "提示", "正在获取单元信息...")

    def on_units_result(self, success, units_data, message):
        if success:
            data = units_data[0]
            self.uid = data['uid']
            self.classid = data['classid']
            self.current_units = data['units']
            
            self.unit_combo.clear()
            self.unit_combo.addItem("全部单元", -1)
            
            for i, unit in enumerate(self.current_units):
                unit_name = unit.get('name', f'单元 {i+1}')
                unit_status = "已开放" if unit.get('visible') == 'true' else "未开放"
                display_text = f"单元 {i+1}: {unit_name} [{unit_status}]"
                self.unit_combo.addItem(display_text, i)
            
            self.unit_combo.setEnabled(True)
            self.start_study_btn.setEnabled(True)
            QMessageBox.information(self, "成功", f"获取到 {len(self.current_units)} 个单元")
        else:
            QMessageBox.warning(self, "失败", message)

    def start_study(self, checked=False):
        if not self.current_course:
            QMessageBox.warning(self, "警告", "请先选择课程")
            return
        
        unit_idx = self.unit_combo.currentData()
        
        if self.mode_combo.currentText() == "刷作业模式":
            if self.accuracy_mode_combo.currentText() == "固定正确率":
                accuracy_config = self.fixed_accuracy_spin.value()
            else:
                range_text = self.random_accuracy_label.text()
                try:
                    min_val, max_val = range_text.replace('%', '').split('-')
                    accuracy_config = (int(min_val), int(max_val))
                except:
                    accuracy_config = (80, 100)
            
            self.start_study_btn.setEnabled(False)
            self.progress_text.append("开始学习...")
            self.study_thread = StudyThread(
                self.session,
                self.current_course['cid'],
                self.uid,
                self.classid,
                unit_idx,
                accuracy_config,
                self.current_units
            )
            self.study_thread.progress_update.connect(self.on_progress_update)
            self.study_thread.study_finished.connect(self.on_study_finished)
            self.study_thread.start()
            
        else:
            if self.time_mode_combo.currentText() == "固定时长":
                time_config = self.fixed_time_spin.value()
            else:
                range_text = self.random_time_label.text()
                try:
                    min_val, max_val = range_text.replace('秒', '').split('-')
                    time_config = (int(min_val), int(max_val))
                except:
                    time_config = (10, 30)
            
            self.start_study_btn.setEnabled(False)
            self.progress_text.append("开始刷时长...")
            self.time_thread = TimeStudyThread(
                self.session,
                self.current_course['cid'],
                self.uid,
                self.classid,
                unit_idx,
                time_config,
                self.current_units
            )
            self.time_thread.progress_update.connect(self.on_progress_update)
            self.time_thread.study_finished.connect(self.on_study_finished)
            self.time_thread.start()
        
        self.tab_widget.setCurrentIndex(2)


    def on_progress_update(self, status, message):
        self.progress_text.append(message)
        self.progress_text.verticalScrollBar().setValue(
            self.progress_text.verticalScrollBar().maximum()
        )

    def on_study_finished(self, result):
        self.study_thread = None
        self.start_study_btn.setEnabled(True)
        
        self.way1_success_label.setText(str(result['way1_succeed']))
        self.way1_fail_label.setText(str(result['way1_failed']))
        self.way2_success_label.setText(str(result['way2_succeed']))
        self.way2_fail_label.setText(str(result['way2_failed']))
        
        self.progress_text.append("\n学习完成！")
        QMessageBox.information(self, "完成", "学习任务已完成")

def main():
    app = QApplication(sys.argv)
    window = WeLearnUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()