import re
import time
import requests
import json
from typing import Dict, List, Optional, Tuple, Any
from core.crypto import generate_cipher_text

class WeLearnClient:
    BASE_URL = "https://welearn.sflep.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.uid = None  # 存储当前登录用户的ID

    def login(self, username, password) -> Tuple[bool, str, Optional[str]]:
        """登录并返回用户ID
        
        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 消息, 用户ID)
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/user/prelogin.aspx?loginret=http://welearn.sflep.com/user/loginredirect.aspx",
                timeout=10,
            )

            if response.status_code != 200:
                return False, f"网络请求失败，状态码: {response.status_code}", None

            url_parts = response.url.split("%26")
            if len(url_parts) < 7:
                return False, "登录URL格式异常", None

            code_challenge = (url_parts[4].split("%3D")[1] if len(url_parts[4].split("%3D")) > 1 else "")
            state = (url_parts[6].split("%3D")[1] if len(url_parts[6].split("%3D")) > 1 else "")

            rturl = (
                f"/connect/authorize/callback?client_id=welearn_web&redirect_uri=https%3A%2F%2Fwelearn.sflep.com%2Fsignin-sflep"
                f"&response_type=code&scope=openid%20profile%20email%20phone%20address&code_challenge={code_challenge}"
                f"&code_challenge_method=S256&state={state}&x-client-SKU=ID_NET472&x-client-ver=6.32.1.0"
            )

            enpwd = generate_cipher_text(password)

            form_data = {
                "rturl": rturl,
                "account": username,
                "pwd": enpwd[0],
                "ts": enpwd[1],
            }

            response = self.session.post(
                "https://sso.sflep.com/idsvr/account/login", data=form_data, timeout=10
            )

            if response.status_code != 200:
                return False, f"登录请求失败，状态码: {response.status_code}", None

            result = response.json()
            code = result.get("code", -1)

            if code == 1:
                return False, "帐号或密码错误", None

            self.session.get(
                f"{self.BASE_URL}/user/prelogin.aspx?loginret=http://welearn.sflep.com/user/loginredirect.aspx",
                timeout=10,
            )

            if code == 0:
                # 登录成功后获取用户ID
                success, uid, message = self.get_user_id()
                if success:
                    self.uid = uid
                    return True, "登录成功", uid
                else:
                    return True, "登录成功（但未能获取用户ID）", None
            else:
                return False, "登录失败", None

        except Exception as e:
            return False, f"登录过程中发生错误: {str(e)}", None

    def get_user_id(self) -> Tuple[bool, str, str]:
        """获取当前登录用户的ID
        
        Returns:
            Tuple[bool, str, str]: (是否成功, 用户ID, 错误信息)
        """
        try:
            # 如果已经获取过用户ID，直接返回
            if self.uid:
                return True, self.uid, "用户ID已缓存"
            
            # 尝试多种页面获取用户ID
            urls_to_try = [
                f"{self.BASE_URL}/2019/student/index.aspx",
                f"{self.BASE_URL}/student/index.aspx",
                f"{self.BASE_URL}/"
            ]
            
            uid = None
            response_content = ""
            
            for url in urls_to_try:
                try:
                    # 访问页面获取用户ID
                    response = self.session.get(url, timeout=10)
                    response_content = response.text
                    
                    if response.status_code != 200:
                        continue
                    
                    # 尝试多种可能的用户ID格式
                    patterns = [
                        # 数字格式的用户ID
                        r'"uid":\s*(\d+),',
                        r'uid\s*[:=]\s*["\']?(\d+)["\']?',
                        r'userid\s*[:=]\s*["\']?(\d+)["\']?',
                        r'user_id\s*[:=]\s*["\']?(\d+)["\']?',
                        r'"UserId":\s*["\']?(\d+)["\']?',
                        r'"studentid":\s*["\']?(\d+)["\']?',
                        r'"studentId":\s*["\']?(\d+)["\']?',
                        r'userid=(\d+)',
                        r'uid=(\d+)',
                        r'userId=(\d+)',
                        r'studentId=(\d+)',
                        r'"id":"(\d+)"',
                        r'\b(\d{7,12})\b',  # 尝试匹配7-12位数字，可能是学生ID
                        # 字符串格式的用户ID（如UUID格式）
                        r'login_success\([^,]+,[^,]+,[^,]+,["\']?([a-f0-9-]{32,64})["\']?',
                        r'var\s+email\s*=\s*["\']?([a-f0-9-]{32,64})["\']?',
                        r'"id":"([a-f0-9-]{32,64})"',
                        r'"uid":"([a-f0-9-]{32,64})"',
                        r'"userid":"([a-f0-9-]{32,64})"',
                    ]
                    
                    for pattern in patterns:
                        uid_match = re.search(pattern, response_content, re.IGNORECASE)
                        if uid_match:
                            uid = uid_match.group(1)
                            break
                    
                    if uid:
                        break
                        
                except Exception as e:
                    continue
            
            # 保存页面内容用于调试
            with open("debug_page_content.html", "w", encoding="utf-8") as f:
                if response_content:
                    f.write(response_content)
                else:
                    f.write("无页面内容可用")
            
            if not uid:
                # 尝试从cookie中获取
                for cookie in self.session.cookies:
                    if 'uid' in cookie.name.lower() or 'userid' in cookie.name.lower():
                        uid = cookie.value
                        break
            
            # 尝试从session中获取
            if not uid:
                for cookie in self.session.cookies:
                    if 'sflep' in cookie.name.lower() or 'welearn' in cookie.name.lower():
                        try:
                            cookie_value = cookie.value
                            # 尝试从cookie值中提取数字ID
                            uid_match = re.search(r'\b(\d+)\b', cookie_value)
                            if uid_match:
                                uid = uid_match.group(1)
                                break
                        except:
                            continue
            
            if not uid:
                return False, "", "无法从页面解析用户ID"
            
            self.uid = uid
            return True, self.uid, "获取用户ID成功"
            
        except Exception as e:
            # 保存异常信息到调试文件
            try:
                with open("debug_page_content.html", "w", encoding="utf-8") as f:
                    f.write(f"异常信息: {str(e)}")
            except:
                pass
            return False, "", f"获取用户ID失败: {str(e)}"

    def get_courses(self) -> Tuple[bool, List, str]:
        try:
            url = f"{self.BASE_URL}/ajax/authCourse.aspx?action=gmc"
            response = self.session.get(
                url,
                headers={"Referer": f"{self.BASE_URL}/2019/student/index.aspx"},
                timeout=10,
            )

            if response.status_code != 200:
                return False, [], f"获取课程失败，状态码: {response.status_code}"

            data = response.json()
            if not data.get("clist"):
                return False, [], "没有找到课程"

            return True, data["clist"], "获取课程成功"
        except Exception as e:
            return False, [], f"获取课程列表失败: {str(e)}"

    def get_course_info(self, cid) -> Tuple[bool, Optional[Dict], str]:
        try:
            url = f"{self.BASE_URL}/student/course_info.aspx?cid={cid}"
            response = self.session.get(url, timeout=10)

            if response.status_code != 200:
                return False, None, f"获取课程信息失败，状态码: {response.status_code}"

            uid_match = re.search(r'"uid":\s*(\d+),', response.text)
            classid_match = re.search(r'"classid":"(\w+)"', response.text)

            if not uid_match or not classid_match:
                return False, None, "无法解析课程信息"

            uid = uid_match.group(1)
            classid = classid_match.group(1)

            url = f"{self.BASE_URL}/ajax/StudyStat.aspx"
            response = self.session.get(
                url,
                params={"action": "courseunits", "cid": cid, "uid": uid},
                headers={"Referer": f"{self.BASE_URL}/2019/student/course_info.aspx"},
                timeout=10,
            )

            if response.status_code != 200:
                return False, None, f"获取单元信息失败，状态码: {response.status_code}"

            data = response.json()
            if "info" not in data:
                return False, None, "单元信息格式错误"

            result_data = {"uid": uid, "classid": classid, "units": data["info"]}
            return True, result_data, "获取单元信息成功"

        except Exception as e:
            return False, None, f"获取课程单元失败: {str(e)}"

    def get_sco_leaves(self, cid, uid, classid, unit_idx) -> Tuple[bool, List, str]:
        try:
            url = f"{self.BASE_URL}/ajax/StudyStat.aspx"
            params = {
                "action": "scoLeaves",
                "cid": cid,
                "uid": uid,
                "unitidx": unit_idx,
                "classid": classid,
            }
            headers = {
                "Referer": f"{self.BASE_URL}/2019/student/course_info.aspx?cid={cid}",
            }

            response = self.session.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            return True, data.get("info", []), "Success"
        except Exception as e:
            return False, [], str(e)

    def submit_course_progress(self, cid, uid, classid, scoid, accuracy) -> Tuple[int, int, int, int]:
        way1_succeed, way1_failed, way2_succeed, way2_failed = 0, 0, 0, 0
        ajax_url = f"{self.BASE_URL}/Ajax/SCO.aspx"
        
        referer = f"{self.BASE_URL}/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={scoid}"

        try:
            data = (
                '{"cmi":{"completion_status":"completed","interactions":[],"launch_data":"","progress_measure":"1",'
                f'"score":{{"scaled":"{accuracy}","raw":"100"}},"session_time":"0","success_status":"unknown",'
                '"total_time":"0","mode":"normal"},"adl":{"data":[]},"cci":{"data":[],"service":{"dictionary":'
                '{"headword":"","short_cuts":""},"new_words":[],"notes":[],"writing_marking":[],"record":'
                '{"files":[]},"play":{"offline_media_id":"9999"}},"retry_count":"0","submit_time":""}}[INTERACTIONINFO]'
            )

            # Action 1: startsco
            self.session.post(
                ajax_url,
                data={
                    "action": "startsco160928",
                    "cid": cid,
                    "scoid": scoid,
                    "uid": uid,
                },
                headers={"Referer": referer},
                timeout=10,
            )

            # Action 2: setscoinfo (Way 1)
            response = self.session.post(
                ajax_url,
                data={
                    "action": "setscoinfo",
                    "cid": cid,
                    "scoid": scoid,
                    "uid": uid,
                    "data": data,
                    "isend": "False",
                },
                headers={"Referer": referer},
                timeout=10,
            )

            if response.status_code == 200 and '"ret":0' in response.text:
                way1_succeed = 1
            else:
                way1_failed = 1

            # Action 3: savescoinfo (Way 2)
            response = self.session.post(
                ajax_url,
                data={
                    "action": "savescoinfo160928",
                    "cid": cid,
                    "scoid": scoid,
                    "uid": uid,
                    "progress": "100",
                    "crate": accuracy,
                    "status": "unknown",
                    "cstatus": "completed",
                    "trycount": "0",
                },
                headers={"Referer": referer},
                timeout=10,
            )

            if response.status_code == 200 and '"ret":0' in response.text:
                way2_succeed = 1
            else:
                way2_failed = 1

        except Exception:
            way1_failed = 1
            way2_failed = 1

        return way1_succeed, way1_failed, way2_succeed, way2_failed

    def simulate_time(self, cid, uid, scoid, learning_time) -> bool:
        try:
            common_data = {"uid": uid, "cid": cid, "scoid": scoid}
            common_headers = {
                "Referer": f"{self.BASE_URL}/student/StudyCourse.aspx"
            }
            ajax_url = f"{self.BASE_URL}/Ajax/SCO.aspx"

            self.session.post(
                ajax_url,
                data={**common_data, "action": "startsco160928"},
                headers=common_headers,
            )

            for current_time in range(1, learning_time + 1):
                time.sleep(1)
                if current_time % 60 == 0:
                    self.session.post(
                        ajax_url,
                        data={
                            **common_data,
                            "action": "keepsco_with_getticket_with_updatecmitime",
                        },
                        headers=common_headers,
                    )

            self.session.post(
                ajax_url,
                data={
                    **common_data,
                    "action": "savescoinfo160928",
                    "progress": "100",
                    "crate": "0",
                    "status": "unknown",
                    "cstatus": "completed",
                    "trycount": "0",
                },
                headers=common_headers,
            )

            return True
        except Exception:
            return False
    



    



    








    def get_user_profile_html(self, uid) -> Tuple[bool, str, str]:
        """直接获取用户资料页的HTML"""
        try:
            url = f"{self.BASE_URL}/user/stuprofile.aspx"
            params = {"uid": uid}
            headers = {
                "Referer": f"{self.BASE_URL}/2019/student/index.aspx",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            response = self.session.get(url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                return False, "", f"访问失败: {response.status_code}"

            # 保存HTML用于调试
            with open(f"debug_profile_{uid}.html", "w", encoding="utf-8") as f:
                f.write(response.text)

            return True, response.text, "获取成功"

        except Exception as e:
            return False, "", str(e)


