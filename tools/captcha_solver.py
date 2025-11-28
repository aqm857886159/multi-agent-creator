import cv2
import numpy as np
import requests
import time
import random
from typing import List, Tuple

class CaptchaSolver:
    """
    移植自 MediaCrawler 的滑块验证码解决方案。
    核心能力:
    1. 识别滑块缺口位置 (OpenCV)
    2. 生成仿人拖动轨迹 (Physics-based)
    """
    
    def __init__(self, page):
        self.page = page

    def solve_slider(self) -> bool:
        """
        尝试自动解决当前页面的滑块验证码。
        返回: True (成功), False (失败)
        """
        print("🧩 检测到验证码，启动自动破解程序...")
        
        try:
            # 1. 获取验证码图片
            # 抖音验证码通常有两个图片: 背景图(bg) 和 滑块图(notch/puzzle)
            # 这里我们需要定位这两个元素。选择器可能随版本变化。
            
            # 尝试常见的选择器 (基于 MediaCrawler 经验)
            bg_ele = self.page.ele('xpath://div[contains(@class,"captcha_verify_img_slide")]//img[contains(@class,"captcha_verify_img_slide")]') or \
                     self.page.ele('css:.captcha_verify_img--wrapper img') 
                     
            if not bg_ele:
                print("⚠️ 未找到验证码背景图，可能选择器已变。")
                return False

            # 下载图片
            bg_url = bg_ele.attr('src')
            if not bg_url: return False
            
            # 保存图片到本地临时文件进行处理
            self._download_img(bg_url, 'captcha_bg.jpg')
            
            # 2. 识别缺口位置
            distance = self._identify_gap('captcha_bg.jpg')
            if not distance:
                print("⚠️ 无法识别缺口位置。")
                return False
                
            # 抖音图片通常有缩放，需要根据网页实际渲染宽度进行比例换算
            # 假设图片原始宽 552 (或其他), 网页渲染宽 276 (或其他)
            # 这里需要动态获取渲染宽度
            rendered_width = bg_ele.rect.size[0]
            natural_width = 552 # 抖音常见原始宽度，可能需要调整
            
            # 简单的比例修正: 既然我们是在下载的图上识别的，distance 是基于原始分辨率的
            # 我们需要按照比例缩放到网页拖动距离
            # 但 DrissionPage/Selenium 的拖动通常是基于像素的。
            # 经验值: 抖音验证码图片可以直接识别，不需要复杂换算，或者 scale = rendered / natural
            scale = rendered_width / natural_width if rendered_width else 0.5
            
            final_distance = int(distance * scale) - 5 # 微调，减去滑块自身的起始偏移
            
            print(f"🎯 识别缺口距离: {distance}, 缩放后: {final_distance}")
            
            # 3. 定位滑块滑块按钮
            slider_btn = self.page.ele('css:.secsdk-captcha-drag-icon') or \
                         self.page.ele('xpath://div[contains(@class,"secsdk-captcha-drag-icon")]')
                         
            if not slider_btn:
                print("⚠️ 未找到滑块按钮。")
                return False
                
            # 4. 生成轨迹并拖动
            tracks = self._generate_tracks(final_distance)
            
            # 执行拖动
            rect = slider_btn.rect
            # 移动到滑块中心
            self.page.actions.move_to(slider_btn)
            self.page.actions.hold()
            
            for track in tracks:
                self.page.actions.move(track, 0, duration=random.uniform(0.01, 0.03))
                
            # 模拟最后的人类抖动
            time.sleep(random.uniform(0.2, 0.5))
            self.page.actions.release()
            
            time.sleep(2)
            
            # 检查是否通过
            if self.page.ele('text:验证成功') or not self.page.ele('css:.captcha_verify_container'):
                print("✅ 滑块验证通过！")
                return True
            else:
                print("❌ 验证失败，重试中...")
                return False

        except Exception as e:
            print(f"❌ 验证码破解异常: {e}")
            return False

    def _download_img(self, url, filename):
        resp = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(resp.content)

    def _identify_gap(self, bg_image_path) -> int:
        """
        使用 Canny 边缘检测识别缺口
        """
        image = cv2.imread(bg_image_path)
        if image is None: return 0
        
        # 灰度化
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 高斯模糊去噪
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Canny 边缘检测
        canny = cv2.Canny(blurred, 200, 450)
        
        contours, hierarchy = cv2.findContours(canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            
            # 抖音缺口特征: 它是正方形的，且在右侧
            # 过滤条件: 面积、长宽比、位置
            if w < 30 or w > 60: continue
            if h < 30 or h > 60: continue
            if x < 50: continue # 缺口不可能在最左边
            
            # 这是一个可能的缺口
            return x
            
        return 0

    def _generate_tracks(self, distance: int) -> List[int]:
        """
        生成符合物理惯性的滑动轨迹
        """
        tracks = []
        current = 0
        mid = distance * 3 / 4
        t = 0.2
        v = 0
        
        while current < distance:
            if current < mid:
                a = 2
            else:
                a = -3
            
            v0 = v
            v = v0 + a * t
            move = v0 * t + 0.5 * a * t * t
            current += move
            tracks.append(round(move))
            
        return tracks

