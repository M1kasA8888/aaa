import streamlit as st
import folium
from streamlit_folium import st_folium
from folium import plugins
import math
import json
import os
import random
import time
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机智能监控系统", page_icon="🛰️", layout="wide")

# ==================== 南京科技职业学院坐标 ====================
CAMPUS = [32.234097, 118.749413]
OBSTACLE_CONFIG_FILE = "obstacle_config.json"
WAYPOINT_CONFIG_FILE = "waypoint_config.json"

# ==================== 初始化 ====================
if 'obstacles' not in st.session_state:
    if os.path.exists(OBSTACLE_CONFIG_FILE):
        try:
            with open(OBSTACLE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.obstacles = data.get('obstacles', [])
        except:
            st.session_state.obstacles = []
    else:
        st.session_state.obstacles = []

if 'point_a' not in st.session_state:
    if os.path.exists(WAYPOINT_CONFIG_FILE):
        try:
            with open(WAYPOINT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.point_a = data.get('point_a', [32.2323, 118.749])
                st.session_state.point_b = data.get('point_b', [32.2344, 118.749])
        except:
            st.session_state.point_a = [32.2323, 118.749]
            st.session_state.point_b = [32.2344, 118.749]
    else:
        st.session_state.point_a = [32.2323, 118.749]
        st.session_state.point_b = [32.2344, 118.749]

if 'flight_alt' not in st.session_state:
    st.session_state.flight_alt = 20
if 'safe_radius' not in st.session_state:
    st.session_state.safe_radius = 5
if 'bypass_distance' not in st.session_state:
    st.session_state.bypass_distance = 20  # 新增：绕行距离控制（米）
if 'route_plans' not in st.session_state:
    st.session_state.route_plans = []
if 'selected_plan' not in st.session_state:
    st.session_state.selected_plan = None
if 'confirmed_plan' not in st.session_state:
    st.session_state.confirmed_plan = None
if 'temp_obs' not in st.session_state:
    st.session_state.temp_obs = None
if 'temp_height' not in st.session_state:
    st.session_state.temp_height = 50
if 'temp_name' not in st.session_state:
    st.session_state.temp_name = "建筑物"
if 'show_height_panel' not in st.session_state:
    st.session_state.show_height_panel = False

# 飞行模拟相关
if "flight_sim_running" not in st.session_state:
    st.session_state.flight_sim_running = False
if "flight_sim_start_time" not in st.session_state:
    st.session_state.flight_sim_start_time = None
if "flight_sim_current_index" not in st.session_state:
    st.session_state.flight_sim_current_index = 0
if "flight_sim_speed" not in st.session_state:
    st.session_state.flight_sim_speed = 8.5
if "flight_sim_waypoints" not in st.session_state:
    st.session_state.flight_sim_waypoints = []
if "flight_sim_total_distance" not in st.session_state:
    st.session_state.flight_sim_total_distance = 0
if "flight_sim_segment_distances" not in st.session_state:
    st.session_state.flight_sim_segment_distances = []
if "flight_sim_last_wp_index" not in st.session_state:
    st.session_state.flight_sim_last_wp_index = -1

# 通信日志相关
if "comm_logs_business" not in st.session_state:
    st.session_state.comm_logs_business = []
if "comm_logs_gcs_to_fcu" not in st.session_state:
    st.session_state.comm_logs_gcs_to_fcu = []
if "comm_logs_fcu_to_gcs" not in st.session_state:
    st.session_state.comm_logs_fcu_to_gcs = []

# ==================== 保存函数 ====================
def save_waypoints():
    data = {'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            'point_a': st.session_state.point_a, 
            'point_b': st.session_state.point_b}
    with open(WAYPOINT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_obstacles_to_file():
    data = {'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            'obstacles': st.session_state.obstacles, 
            'count': len(st.session_state.obstacles)}
    with open(OBSTACLE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_obstacles_from_file():
    if os.path.exists(OBSTACLE_CONFIG_FILE):
        with open(OBSTACLE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            st.session_state.obstacles = data.get('obstacles', [])
        return True
    return False

# ==================== 通信日志辅助函数 ====================
def add_business_log(message, source="OBC 内部", color="green"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.comm_logs_business.append({
        "timestamp": timestamp,
        "message": message,
        "source": source,
        "color": color
    })

def add_gcs_to_fcu_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.comm_logs_gcs_to_fcu.append(f"[{timestamp}] {message}")

def add_fcu_to_gcs_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.comm_logs_fcu_to_gcs.append(f"[{timestamp}] {message}")

def clear_all_logs():
    st.session_state.comm_logs_business = []
    st.session_state.comm_logs_gcs_to_fcu = []
    st.session_state.comm_logs_fcu_to_gcs = []

# ==================== 心跳模拟器 ====================
class HeartbeatSimulator:
    def __init__(self):
        self.running = False
        self.last_time = None
        self.offline = False
        self.history = []
    
    def start(self):
        self.running = True
        self.offline = False
        self.history = []
        self.last_time = time.time()
    
    def stop(self):
        self.running = False
    
    def update(self):
        if not self.running:
            return None
        current = time.time()
        elapsed = current - self.last_time
        if elapsed >= 1:
            self.last_time = current
            heartbeat = {'id': len(self.history) + 1, 
                        'time': datetime.now().strftime("%H:%M:%S"), 
                        'status': 'alive', 
                        'delay': round(random.uniform(5, 50), 2)}
            self.history.append(heartbeat)
            if len(self.history) > 50:
                self.history.pop(0)
            return heartbeat
        if elapsed > 3 and not self.offline:
            self.offline = True
            timeout = {'id': len(self.history) + 1, 
                      'time': datetime.now().strftime("%H:%M:%S"), 
                      'status': 'timeout', 
                      'delay': 0}
            self.history.append(timeout)
            return timeout
        elif elapsed <= 3 and self.offline:
            self.offline = False
        return None
    
    def get_stats(self):
        if not self.history:
            return {'total': 0, 'timeout': 0, 'rate': 100}
        total = len(self.history)
        timeout = sum(1 for h in self.history if h['status'] == 'timeout')
        return {'total': total, 'timeout': timeout, 'rate': round((total-timeout)/total*100, 1)}
    
    def get_history(self):
        return self.history.copy()

if 'heartbeat_sim' not in st.session_state:
    st.session_state.heartbeat_sim = HeartbeatSimulator()
if 'heartbeat_running' not in st.session_state:
    st.session_state.heartbeat_running = False

# ==================== 几何计算函数 ====================
def calc_distance(p1, p2):
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    R = 6371000
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def point_in_polygon(point, poly):
    x, y = point[1], point[0]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
            inside = not inside
    return inside

def calculate_distances(waypoints):
    """计算航点间距离"""
    total = 0
    segment_distances = []
    for i in range(len(waypoints) - 1):
        dist = calc_distance(waypoints[i], waypoints[i+1])
        segment_distances.append(dist)
        total += dist
    return total, segment_distances

def get_polygon_bounds(points):
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return min(lats), max(lats), min(lons), max(lons)

# ==================== 障碍物类 ====================
class Obstacle:
    def __init__(self, points, height, name):
        self.points = points
        self.height = height
        self.name = name
        self.min_lat, self.max_lat, self.min_lon, self.max_lon = get_polygon_bounds(points)
        self.center_lat = (self.min_lat + self.max_lat) / 2
        self.center_lon = (self.min_lon + self.max_lon) / 2
        self.width_lat = self.max_lat - self.min_lat
        self.width_lon = self.max_lon - self.min_lon
        
    def to_dict(self):
        return {'points': self.points, 'height': self.height, 'name': self.name}
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['points'], data['height'], data['name'])
    
    def contains(self, point):
        return point_in_polygon(point, self.points)
    
    def line_intersects(self, start, end):
        """检查线段是否与障碍物相交"""
        for t in range(31):
            t = t/30
            lat = start[0] + (end[0]-start[0])*t
            lon = start[1] + (end[1]-start[1])*t
            if self.contains([lat, lon]):
                return True
        return False
    
    def get_vertex_bypass(self, start, end, side, safe_radius=5, bypass_distance=20):
        """使用障碍物顶点进行绕行，增加绕行距离控制"""
        # 绕行距离 = 安全半径 + 用户设置的绕行距离
        total_offset = safe_radius + bypass_distance
        safe_deg = total_offset / 111000  # 转换为度数
        
        vertices = [
            [self.min_lat, self.min_lon],
            [self.min_lat, self.max_lon],
            [self.max_lat, self.min_lon],
            [self.max_lat, self.max_lon]
        ]
        
        def point_to_line_dist(p, s, e):
            dx = e[0] - s[0]
            dy = e[1] - s[1]
            if dx == 0 and dy == 0:
                return math.hypot(p[0]-s[0], p[1]-s[1])
            t = ((p[0]-s[0])*dx + (p[1]-s[1])*dy) / (dx*dx + dy*dy)
            t = max(0, min(1, t))
            proj_x = s[0] + t * dx
            proj_y = s[1] + t * dy
            return math.hypot(p[0]-proj_x, p[1]-proj_y), [proj_x, proj_y]
        
        best_vertex = None
        best_dist = float('inf')
        
        for vertex in vertices:
            dist, _ = point_to_line_dist(vertex, start, end)
            if dist < best_dist:
                best_dist = dist
                best_vertex = vertex
        
        if best_vertex is None:
            best_vertex = [self.center_lat, self.center_lon]
        
        # 计算航线垂直方向
        dx = end[1] - start[1]
        dy = end[0] - start[0]
        length = math.hypot(dx, dy)
        if length > 0:
            dx /= length
            dy /= length
        
        perp_x = -dy
        perp_y = dx
        
        if side == 'right':
            perp_x = -perp_x
            perp_y = -perp_y
        
        # 应用绕行距离
        bypass = [
            best_vertex[0] + perp_y * safe_deg,
            best_vertex[1] + perp_x * safe_deg
        ]
        
        return bypass

# ==================== 路径规划 ====================
def find_blocking_obstacles(start, end, obstacles, flight_alt):
    """找到所有需要绕行的障碍物"""
    blocking = []
    for obs_data in obstacles:
        if isinstance(obs_data, dict):
            if flight_alt < obs_data['height']:
                obs = Obstacle.from_dict(obs_data)
                if obs.line_intersects(start, end):
                    blocking.append(obs)
        else:
            if flight_alt < obs_data.height:
                if obs_data.line_intersects(start, end):
                    blocking.append(obs_data)
    return blocking

def plan_bypass_path(start, end, obstacles, flight_alt, safe_radius, bypass_distance, side):
    """规划绕行路径"""
    waypoints = [start]
    current_start = start
    current_end = end
    
    blocking = find_blocking_obstacles(current_start, current_end, obstacles, flight_alt)
    
    if not blocking:
        waypoints.append(end)
        return waypoints
    
    def dist_to_start(obs):
        return calc_distance([obs.center_lat, obs.center_lon], start)
    blocking.sort(key=dist_to_start)
    
    for obs in blocking:
        bypass = obs.get_vertex_bypass(current_start, current_end, side, safe_radius, bypass_distance)
        waypoints.append(bypass)
        current_start = bypass
        
        remaining_blocking = find_blocking_obstacles(current_start, current_end, obstacles, flight_alt)
        if not remaining_blocking:
            break
    
    waypoints.append(end)
    
    # 简化路径
    simplified = [waypoints[0]]
    for i in range(1, len(waypoints)-1):
        p1 = simplified[-1]
        p2 = waypoints[i]
        p3 = waypoints[i+1]
        
        skip_safe = True
        for obs_data in obstacles:
            if isinstance(obs_data, dict):
                if flight_alt < obs_data['height']:
                    obs = Obstacle.from_dict(obs_data)
                    if obs.line_intersects(p1, p3):
                        skip_safe = False
                        break
            else:
                if flight_alt < obs_data.height:
                    if obs_data.line_intersects(p1, p3):
                        skip_safe = False
                        break
        
        if not skip_safe:
            simplified.append(p2)
    
    simplified.append(waypoints[-1])
    return simplified

# ==================== 标题 ====================
st.title("🛰️ 无人机智能监控系统")
st.markdown("**南京科技职业学院** | 贴近障碍物绕行 | 多障碍物连续绕行")
st.markdown("---")

# ==================== 侧边栏 ====================
with st.sidebar:
    st.subheader("🌐 坐标系")
    coord_type = st.selectbox("输入坐标系", ["WGS-84", "GCJ-02 (高德/百度)"])
    st.markdown("---")
    st.subheader("📊 系统状态")
    st.success("✅ 系统正常")

# ==================== 标签页 ====================
tab1, tab2 = st.tabs(["🗺️ 航线规划", "📡 飞行监控"])

# ==================== Tab 1: 航线规划 ====================
with tab1:
    col_left, col_right = st.columns([1.5, 1])
    
    with col_left:
        st.subheader("🗺️ 卫星地图")
        
        m = folium.Map(location=CAMPUS, zoom_start=17, control_scale=True)
        folium.TileLayer('https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
                         attr='高德卫星', subdomains=['1','2','3','4']).add_to(m)
        folium.TileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                         attr='OpenStreetMap', name='街道地图').add_to(m)
        folium.Marker(CAMPUS, popup="🏫 南京科技职业学院", icon=folium.Icon(color='red')).add_to(m)
        
        alt = st.session_state.flight_alt
        for obs_data in st.session_state.obstacles:
            if isinstance(obs_data, dict):
                points = obs_data['points']
                height = obs_data['height']
                name = obs_data['name']
            else:
                points = obs_data.points
                height = obs_data.height
                name = obs_data.name
            
            color = 'red' if alt < height else 'green'
            folium.Polygon(points, color=color, weight=2, fill=True, 
                          fill_color=color, fill_opacity=0.3,
                          popup=f"{name}\n高度: {height}m").add_to(m)
        
        folium.Marker(st.session_state.point_a, popup="🚁 起点A", icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(st.session_state.point_b, popup="🎯 终点B", icon=folium.Icon(color='red')).add_to(m)
        
        if st.session_state.selected_plan:
            p = st.session_state.selected_plan
            folium.PolyLine(p['points'], color=p['color'], weight=4, opacity=0.9).add_to(m)
            for i, wp in enumerate(p['points'][1:-1], 1):
                folium.Marker(wp, popup=f"绕行点{i}", icon=folium.Icon(color='purple', icon='refresh')).add_to(m)
        
        plugins.Draw(draw_options={'polygon': {'allowIntersection': False}}).add_to(m)
        plugins.MeasureControl().add_to(m)
        folium.LayerControl().add_to(m)
        
        output = st_folium(m, width=650, height=450, key="map")
        
        if output and output.get('last_active_drawing'):
            d = output['last_active_drawing']
            if d and d['geometry']['type'] == 'Polygon':
                pts = [[c[1], c[0]] for c in d['geometry']['coordinates'][0]]
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 已绘制 {len(pts)} 个点")
    
    with col_right:
        # 新建障碍物
        if st.session_state.show_height_panel and st.session_state.temp_obs:
            st.markdown("### 🆕 新建3D障碍物")
            name = st.text_input("名称", value=st.session_state.temp_name)
            st.session_state.temp_name = name if name else "建筑物"
            
            height = st.number_input("障碍物高度 (m)", value=st.session_state.temp_height, min_value=1, max_value=200, step=5)
            st.session_state.temp_height = height
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 保存", type="primary", use_container_width=True):
                    new_obs = {'points': st.session_state.temp_obs, 'height': height, 'name': st.session_state.temp_name}
                    st.session_state.obstacles.append(new_obs)
                    save_obstacles_to_file()
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            with col2:
                if st.button("🗑️ 取消", use_container_width=True):
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            st.markdown("---")
        
        # 起点
        st.markdown("### 🚁 起点 A")
        col1, col2 = st.columns(2)
        with col1:
            la = st.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
        with col2:
            lo = st.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("📍 设置A点", use_container_width=True):
            st.session_state.point_a = [la, lo]
            save_waypoints()
            st.rerun()
        
        # 终点
        st.markdown("### 🎯 终点 B")
        col1, col2 = st.columns(2)
        with col1:
            lb = st.number_input("纬度", value=st.session_state.point_b[0], format="%.6f", key="lb")
        with col2:
            lob = st.number_input("经度", value=st.session_state.point_b[1], format="%.6f", key="lob")
        if st.button("🏁 设置B点", use_container_width=True):
            st.session_state.point_b = [lb, lob]
            save_waypoints()
            st.rerun()
        
        st.markdown("---")
        
        # 飞行参数
        st.markdown("### ⚙️ 飞行参数")
        alt = st.slider("飞行高度 (m)", 10, 150, st.session_state.flight_alt)
        st.session_state.flight_alt = alt
        safe_radius = st.slider("安全半径 (m)", 1, 30, st.session_state.safe_radius)
        st.session_state.safe_radius = safe_radius
        
        # 新增：绕行距离控制
        bypass_distance = st.slider("绕行距离 (m)", 5, 80, st.session_state.bypass_distance, 
                                     help="无人机绕过障碍物时与障碍物的距离，越大绕得越远")
        st.session_state.bypass_distance = bypass_distance
        
        # 高度检测
        if st.session_state.obstacles:
            st.markdown("**📊 高度检测**")
            for obs_data in st.session_state.obstacles:
                name = obs_data['name'] if isinstance(obs_data, dict) else obs_data.name
                height = obs_data['height'] if isinstance(obs_data, dict) else obs_data.height
                if alt < height:
                    st.warning(f"🔄 低于「{name}」({height}m)，将绕行")
                else:
                    st.success(f"✅ 高于「{name}」({height}m)，可飞越")
        
        st.markdown("---")
        
        # 障碍物列表
        st.markdown("### 🚧 障碍物列表")
        for i, obs_data in enumerate(st.session_state.obstacles):
            name = obs_data['name'] if isinstance(obs_data, dict) else obs_data.name
            height = obs_data['height'] if isinstance(obs_data, dict) else obs_data.height
            icon = "🔄" if alt < height else "⬆️"
            with st.expander(f"{icon} {name} (高度: {height}m)"):
                if st.button(f"删除", key=f"del_{i}"):
                    st.session_state.obstacles.pop(i)
                    save_obstacles_to_file()
                    st.rerun()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 保存", use_container_width=True):
                save_obstacles_to_file()
                st.success("已保存")
        with col2:
            if st.button("📂 加载", use_container_width=True):
                load_obstacles_from_file()
                st.rerun()
        with col3:
            if st.button("🗑️ 清空", use_container_width=True):
                st.session_state.obstacles = []
                save_obstacles_to_file()
                st.rerun()
        
        st.markdown("---")
        st.markdown("## 🗺️ 多航线规划")
        
        # 生成航线方案
        if st.button("🎯 生成航线方案", use_container_width=True, type="primary"):
            start = st.session_state.point_a
            end = st.session_state.point_b
            straight_dist = calc_distance(start, end)
            
            blocking = find_blocking_obstacles(start, end, st.session_state.obstacles, alt)
            
            plans = []
            
            if not blocking:
                plans.append({'name': '📏 直线飞越', 'points': [start, end], 
                             'dist': straight_dist, 'color': 'blue', 
                             'desc': '✅ 无障碍物'})
            else:
                # 左绕行
                left_path = plan_bypass_path(start, end, st.session_state.obstacles, alt, safe_radius, bypass_distance, 'left')
                left_dist = sum(calc_distance(left_path[i], left_path[i+1]) for i in range(len(left_path)-1))
                plans.append({'name': '⬅️ 左绕行', 'points': left_path, 'dist': left_dist, 
                             'color': 'orange', 'desc': f'多走{left_dist-straight_dist:.0f}m'})
                
                # 右绕行
                right_path = plan_bypass_path(start, end, st.session_state.obstacles, alt, safe_radius, bypass_distance, 'right')
                right_dist = sum(calc_distance(right_path[i], right_path[i+1]) for i in range(len(right_path)-1))
                plans.append({'name': '➡️ 右绕行', 'points': right_path, 'dist': right_dist, 
                             'color': 'purple', 'desc': f'多走{right_dist-straight_dist:.0f}m'})
                
                # 最佳航线
                best = min(plans, key=lambda x: x['dist']).copy()
                best['name'] = '⭐ 最佳航线'
                best['color'] = 'gold'
                best['desc'] = f'最优路径，省{abs(plans[0]["dist"] - plans[1]["dist"]):.0f}m'
                plans.append(best)
            
            st.session_state.route_plans = plans
            st.session_state.selected_plan = plans[-1]
            st.rerun()
        
        # 显示方案
        if st.session_state.route_plans:
            st.markdown("---")
            st.markdown("### 📋 可选方案")
            
            for i, p in enumerate(st.session_state.route_plans):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    if "左绕行" in p['name']:
                        st.markdown(f"**🟠 {p['name']}**")
                    elif "右绕行" in p['name']:
                        st.markdown(f"**🟣 {p['name']}**")
                    elif "最佳" in p['name']:
                        st.markdown(f"**⭐ {p['name']}**")
                    else:
                        st.markdown(f"**🔵 {p['name']}**")
                    st.caption(p['desc'])
                with col2:
                    st.metric("距离", f"{p['dist']:.0f}m")
                with col3:
                    st.metric("时间", f"{p['dist']/15:.0f}s")
                
                if st.session_state.selected_plan and st.session_state.selected_plan['name'] == p['name']:
                    st.success("✅ 已选中")
                else:
                    if st.button(f"选择此方案", key=f"sel_{i}", use_container_width=True):
                        st.session_state.selected_plan = p
                        st.rerun()
                st.markdown("---")
            
            if st.session_state.selected_plan:
                p = st.session_state.selected_plan
                straight = calc_distance(st.session_state.point_a, st.session_state.point_b)
                st.info(f"**当前: {p['name']}** | {p['dist']:.0f}m | 比直线多: {p['dist']-straight:.0f}m")
                if st.button("✈️ 确认使用", use_container_width=True, type="primary"):
                    st.session_state.confirmed_plan = p
                    st.success(f"✅ 已确认")
                    st.balloons()
        
        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 当前航线")
            p = st.session_state.confirmed_plan
            st.success(f"**{p['name']}**")
            st.caption(f"距离: {p['dist']:.0f}m | 时间: {p['dist']/15:.0f}s")

# ==================== Tab 2: 飞行监控 ====================
with tab2:
    st.subheader("📡 飞行实时画面 - 任务执行监控")
    
    # 侧边栏控制（在页面内）
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.markdown("### 🎮 飞行控制")
        
        # 导入航线按钮
        if st.button("📐 导入当前航线", use_container_width=True):
            start = st.session_state.point_a
            end = st.session_state.point_b
            waypoints = plan_bypass_path(
                start, end, st.session_state.obstacles,
                st.session_state.flight_alt, st.session_state.safe_radius,
                st.session_state.bypass_distance, 'best'
            )
            total_dist, seg_dists = calculate_distances(waypoints)
            st.session_state.flight_sim_waypoints = waypoints
            st.session_state.flight_sim_total_distance = total_dist
            st.session_state.flight_sim_segment_distances = seg_dists
            st.session_state.flight_sim_current_index = 0
            st.session_state.flight_sim_running = False
            st.session_state.flight_sim_start_time = None
            st.session_state.flight_sim_last_wp_index = -1
            clear_all_logs()
            add_business_log(f"航线规划完成 | 航点数: {len(waypoints)} | 路径长度: {total_dist:.1f}m", color="green")
            add_gcs_to_fcu_log("GCS→OBC: MISSION_UPLOAD")
            add_fcu_to_gcs_log("FCU→OBC: MISSION_ACK")
            st.success(f"✅ 航线已导入，共 {len(waypoints)} 个航点")
            st.rerun()
        
        waypoints = st.session_state.flight_sim_waypoints
        seg_dists = st.session_state.flight_sim_segment_distances
        total_dist = st.session_state.flight_sim_total_distance
        
        st.markdown("---")
        
        # 速度控制
        speed = st.slider("飞行速度 (m/s)", 1.0, 20.0, st.session_state.flight_sim_speed, 0.5)
        st.session_state.flight_sim_speed = speed
        
        st.markdown("---")
        
        # 控制按钮
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("▶️ 开始", use_container_width=True, disabled=len(waypoints) == 0):
                st.session_state.flight_sim_running = True
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                add_fcu_to_gcs_log("FCU→OBC→GCS: ACK | Mode: AUTO")
                st.rerun()
        with col2:
            if st.button("⏹️ 停止", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.rerun()
        with col3:
            if st.button("🔄 重置", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_current_index = 0
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 航线信息")
        st.caption(f"起点A: {st.session_state.point_a[0]:.6f}, {st.session_state.point_a[1]:.6f}")
        st.caption(f"终点B: {st.session_state.point_b[0]:.6f}, {st.session_state.point_b[1]:.6f}")
        st.caption(f"飞行高度: {st.session_state.flight_alt} m")
        st.caption(f"安全半径: {st.session_state.safe_radius} m")
        st.caption(f"绕行距离: {st.session_state.bypass_distance} m")
        st.caption(f"航点数量: {len(waypoints)}")
        if total_dist > 0:
            st.caption(f"总距离: {total_dist:.1f} 米")
        
        st.markdown("---")
        st.markdown("### 💓 心跳监控")
        
        if not st.session_state.heartbeat_running:
            if st.button("▶️ 启动心跳", use_container_width=True):
                st.session_state.heartbeat_sim.start()
                st.session_state.heartbeat_running = True
                st.rerun()
        else:
            if st.button("⏹️ 停止心跳", use_container_width=True):
                st.session_state.heartbeat_sim.stop()
                st.session_state.heartbeat_running = False
                st.rerun()
        
        hb = st.session_state.heartbeat_sim.update()
        if hb:
            if hb['status'] == 'timeout':
                st.error(f"⚠️ 连接超时！3秒未收到心跳")
            else:
                st.success(f"💓 心跳正常 | ID: {hb['id']} | 延迟: {hb['delay']}ms")
        
        stats = st.session_state.heartbeat_sim.get_stats()
        col1, col2 = st.columns(2)
        col1.metric("总心跳", stats['total'])
        col2.metric("成功率", f"{stats['rate']}%")
    
    with col_right:
        # 飞行状态显示
        if len(waypoints) > 0:
            # 计算当前飞行状态
            if st.session_state.flight_sim_running:
                elapsed_time = time.time() - st.session_state.flight_sim_start_time
                current_speed = st.session_state.flight_sim_speed
                flown_distance = elapsed_time * current_speed
                
                total_flown = 0
                current_index = 0
                segment_progress = 0
                
                for i, seg_dist in enumerate(seg_dists):
                    if total_flown + seg_dist >= flown_distance:
                        current_index = i
                        if seg_dist > 0:
                            segment_progress = (flown_distance - total_flown) / seg_dist
                        break
                    total_flown += seg_dist
                else:
                    current_index = len(waypoints) - 1
                    segment_progress = 1
                    st.session_state.flight_sim_running = False
                
                st.session_state.flight_sim_current_index = current_index
                
                p1 = waypoints[current_index]
                p2_index = min(current_index + 1, len(waypoints) - 1)
                p2 = waypoints[p2_index]
                current_lng = p1[0] + (p2[0] - p1[0]) * segment_progress
                current_lat = p1[1] + (p2[1] - p1[1]) * segment_progress
                
                remaining_distance = max(0, total_dist - flown_distance)
                remaining_time = remaining_distance / current_speed if current_speed > 0 else 0
                
                hours = int(elapsed_time // 3600)
                minutes = int((elapsed_time % 3600) // 60)
                seconds = int(elapsed_time % 60)
                elapsed_str = f"{minutes:02d}:{seconds:02d}" if hours == 0 else f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                rem_minutes = int(remaining_time // 60)
                rem_seconds = int(remaining_time % 60)
                remaining_str = f"{rem_minutes:02d}:{rem_seconds:02d}"
                
                battery_remaining = max(0, 100 - (elapsed_time / 1800) * 100)
                
                # 航点到达日志
                if current_index > st.session_state.flight_sim_last_wp_index:
                    st.session_state.flight_sim_last_wp_index = current_index
                    add_fcu_to_gcs_log(f"FCU→OBC→GCS: WP_REACHED #{current_index}")
                    if current_index >= len(waypoints) - 1:
                        add_fcu_to_gcs_log("FCU→OBC→GCS: MISSION_COMPLETE")
                        add_business_log("任务执行完成", color="green")
            else:
                current_lng = waypoints[0][0]
                current_lat = waypoints[0][1]
                flown_distance = 0
                remaining_distance = total_dist
                elapsed_str = "00:00"
                remaining_str = "00:00"
                battery_remaining = 100
                current_index = 0
            
            # 仪表盘
            st.markdown("### 📊 飞行数据")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("当前航点", f"{min(current_index + 1, len(waypoints))}/{len(waypoints)}")
            col2.metric("飞行速度", f"{st.session_state.flight_sim_speed:.1f} m/s")
            col3.metric("已用时间", elapsed_str)
            col4.metric("剩余距离", f"{remaining_distance:.0f} m")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("预计到达", remaining_str)
            col2.metric("电量模拟", f"{battery_remaining:.0f}%")
            col3.metric("完成进度", f"{(flown_distance/total_dist*100) if total_dist > 0 else 0:.0f}%")
            
            # 进度条
            if total_dist > 0:
                st.progress(min(1.0, flown_distance / total_dist))
            
            st.markdown("---")
            
            # 通信链路拓扑
            st.markdown("### 📶 通信链路拓扑")
            
            col_gcs, col_obc, col_fcu = st.columns(3)
            with col_gcs:
                st.success("✅ GCS 在线")
            with col_obc:
                st.success("✅ OBC 在线")
            with col_fcu:
                st.success("✅ FCU 在线")
            
            st.markdown("---")
            
            # 当前状态
            if st.session_state.flight_sim_running:
                st.info("✈️ 任务执行中...")
            elif current_index >= len(waypoints) - 1 and len(waypoints) > 0:
                st.success("✅ 任务已完成！")
            else:
                st.info("⏸️ 等待开始")
            
            # 通信日志
            st.markdown("---")
            st.markdown("### 📝 通信日志")
            
            log_container = st.container(height=200)
            with log_container:
                for log in st.session_state.comm_logs_business[-10:]:
                    st.caption(f"📋 [{log['timestamp']}] {log['message']}")
                
                for log in st.session_state.comm_logs_fcu_to_gcs[-5:]:
                    st.caption(f"⬆️ {log}")
                
                for log in st.session_state.comm_logs_gcs_to_fcu[-5:]:
                    st.caption(f"⬇️ {log}")
            
            # 自动刷新
            if st.session_state.flight_sim_running:
                time.sleep(1)
                st.rerun()
        else:
            st.info("请先点击「导入当前航线」加载航线")

st.markdown("---")
st.caption("💡 **步骤**: ①画多边形 → ②设置高度和绕行距离 → ③生成方案 → ④切换到飞行监控 → ⑤导入航线 → ⑥开始飞行")
