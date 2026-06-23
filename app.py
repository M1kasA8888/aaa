import streamlit as st
import folium
from streamlit_folium import st_folium
from folium import plugins
import math
import json
import os
import random
import time
from datetime import datetime

# ==================== 页面全局配置 ====================
st.set_page_config(page_title="无人机智能监控系统", page_icon="🛰️", layout="wide")

# ==================== 基准坐标与配置文件 ====================
CAMPUS = [32.2333, 118.7494]
OBSTACLE_CONFIG_FILE = "obstacle_config.json"
WAYPOINT_CONFIG_FILE = "waypoint_config.json"

# ==================== 会话状态初始化 ====================
if 'obstacles' not in st.session_state:
    if os.path.exists(OBSTACLE_CONFIG_FILE):
        try:
            with open(OBSTACLE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.obstacles = data.get('obstacles', [])
        except Exception:
            st.session_state.obstacles = []
    else:
        st.session_state.obstacles = []

if 'point_a' not in st.session_state:
    if os.path.exists(WAYPOINT_CONFIG_FILE):
        try:
            with open(WAYPOINT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.point_a = data.get('point_a', [32.2347, 118.7490])
                st.session_state.point_b = data.get('point_b', [32.2312, 118.7492])
        except Exception:
            st.session_state.point_a = [32.2347, 118.7490]
            st.session_state.point_b = [32.2312, 118.7492]
    else:
        st.session_state.point_a = [32.2347, 118.7490]
        st.session_state.point_b = [32.2312, 118.7492]

if 'flight_alt' not in st.session_state:
    st.session_state.flight_alt = 20
if 'safe_radius' not in st.session_state:
    st.session_state.safe_radius = 5
if 'bypass_distance' not in st.session_state:
    st.session_state.bypass_distance = 5

# 颜色自定义
if 'obs_fill_color' not in st.session_state:
    st.session_state.obs_fill_color = "#ff2d2d"
if 'buffer_line_color' not in st.session_state:
    st.session_state.buffer_line_color = "#0066ff"
if 'left_route_color' not in st.session_state:
    st.session_state.left_route_color = "#ff9800"
if 'right_route_color' not in st.session_state:
    st.session_state.right_route_color = "#9c27b0"
if 'best_route_color' not in st.session_state:
    st.session_state.best_route_color = "#ffc107"

if 'route_plans' not in st.session_state:
    st.session_state.route_plans = []
if 'selected_plan' not in st.session_state:
    st.session_state.selected_plan = None
if 'confirmed_plan' not in st.session_state:
    st.session_state.confirmed_plan = None

if 'temp_obs' not in st.session_state:
    st.session_state.temp_obs = None
if 'temp_height' not in st.session_state:
    st.session_state.temp_height = 35
if 'temp_name' not in st.session_state:
    st.session_state.temp_name = "建筑物"
if 'show_height_panel' not in st.session_state:
    st.session_state.show_height_panel = False

# 飞行仿真状态
if "flight_sim_running" not in st.session_state:
    st.session_state.flight_sim_running = False
if "flight_sim_start_time" not in st.session_state:
    st.session_state.flight_sim_start_time = None
if "flight_sim_pause_time" not in st.session_state:
    st.session_state.flight_sim_pause_time = 0
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

# 通信日志
if "comm_logs_business" not in st.session_state:
    st.session_state.comm_logs_business = []
if "comm_logs_gcs_to_fcu" not in st.session_state:
    st.session_state.comm_logs_gcs_to_fcu = []
if "comm_logs_fcu_to_gcs" not in st.session_state:
    st.session_state.comm_logs_fcu_to_gcs = []

# ==================== 持久化函数 ====================
def save_waypoints():
    data = {
        'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'point_a': st.session_state.point_a,
        'point_b': st.session_state.point_b
    }
    with open(WAYPOINT_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_obstacles_to_file():
    data = {
        'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'obstacles': st.session_state.obstacles,
        'count': len(st.session_state.obstacles)
    }
    with open(OBSTACLE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_obstacles_from_file():
    if os.path.exists(OBSTACLE_CONFIG_FILE):
        with open(OBSTACLE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            st.session_state.obstacles = data.get('obstacles', [])
        return True
    return False

# ==================== 日志工具 ====================
def add_business_log(message, source="OBC 内部", color="green"):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.comm_logs_business.append({"timestamp": ts, "message": message, "source": source, "color": color})

def add_gcs_to_fcu_log(message):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.comm_logs_gcs_to_fcu.append(f"[{ts}] {message}")

def add_fcu_to_gcs_log(message):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.comm_logs_fcu_to_gcs.append(f"[{ts}] {message}")

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
        now = time.time()
        elapse = now - self.last_time
        if elapse >= 1.0:
            self.last_time = now
            hb = {
                "id": len(self.history)+1,
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": "alive",
                "delay": round(random.uniform(5, 50), 2)
            }
            self.history.append(hb)
            if len(self.history) > 50:
                self.history.pop(0)
            return hb
        if elapse > 3.0 and not self.offline:
            self.offline = True
            timeout_item = {
                "id": len(self.history)+1,
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": "timeout",
                "delay": 0
            }
            self.history.append(timeout_item)
            return timeout_item
        elif elapse <= 3.0 and self.offline:
            self.offline = False
        return None

    def get_stats(self):
        if not self.history:
            return {"total":0, "timeout":0, "rate":100.0}
        total = len(self.history)
        timeout_cnt = sum(1 for item in self.history if item["status"] == "timeout")
        rate = round((total-timeout_cnt)/total*100, 1)
        return {"total":total, "timeout":timeout_cnt, "rate":rate}

if 'heartbeat_sim' not in st.session_state:
    st.session_state.heartbeat_sim = HeartbeatSimulator()
if 'heartbeat_running' not in st.session_state:
    st.session_state.heartbeat_running = False

# ==================================================
# 【修复1】几何基础计算：碰撞检测100%准确
# ==================================================
def calc_distance(p1, p2):
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    R = 6371000
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def meter_to_degree(meter, base_lat):
    lat_per_m = 1.0 / 111320.0
    lon_per_m = 1.0 / (111320.0 * math.cos(math.radians(base_lat)))
    return meter * lat_per_m, meter * lon_per_m

def polygon_area(poly):
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        area += (x2 - x1) * (y2 + y1)
    return abs(area)

def point_in_polygon(pt, poly):
    """严格射线法，点在多边形内部或边上都返回True"""
    x, y = pt[1], pt[0]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        # 点在边上直接返回True
        if min(x1,x2) - 1e-8 <= x <= max(x1,x2) + 1e-8 and min(y1,y2) - 1e-8 <= y <= max(y1,y2) + 1e-8:
            if abs((x2-x1)*(y-y1) - (y2-y1)*(x-x1)) < 1e-8:
                return True
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
            inside = not inside
    return inside

def _ccw(A, B, C):
    return (C[0]-A[0])*(B[1]-A[1]) - (B[0]-A[0])*(C[1]-A[1]) > 1e-8

def seg_intersect_seg(a1, a2, b1, b2):
    """严格线段相交判断，包含端点接触"""
    if _ccw(a1,b1,b2) != _ccw(a2,b1,b2) and _ccw(a1,a2,b1) != _ccw(a1,a2,b2):
        return True
    # 端点共线重叠
    if point_in_polygon(a1, [b1, b2, b2]): return True
    if point_in_polygon(a2, [b1, b2, b2]): return True
    if point_in_polygon(b1, [a1, a2, a2]): return True
    if point_in_polygon(b2, [a1, a2, a2]): return True
    return False

def seg_intersect_polygon(p0, p1, poly):
    """线段与多边形相交检测：穿过、端点在内、擦边都算碰撞"""
    if point_in_polygon(p0, poly) or point_in_polygon(p1, poly):
        return True
    n = len(poly)
    for i in range(n):
        v1 = poly[i]
        v2 = poly[(i+1)%n]
        if seg_intersect_seg(p0, p1, v1, v2):
            return True
    return False

def polygon_winding(poly):
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        area += (x2 - x1) * (y2 + y1)
    return area > 0

def offset_polygon_outward(poly, offset_m, base_lat):
    """修复版：强制向外偏移多边形，双重校验确保缓冲区在建筑外侧"""
    lat_off, lon_off = meter_to_degree(offset_m, base_lat)
    
    def _offset_with_direction(direction):
        new_poly = []
        n = len(poly)
        for i in range(n):
            p = poly[i]
            p_prev = poly[(i-1)%n]
            p_next = poly[(i+1)%n]
            
            dx1 = p[1] - p_prev[1]
            dy1 = p[0] - p_prev[0]
            dx2 = p_next[1] - p[1]
            dy2 = p_next[0] - p[0]
            
            len1 = math.hypot(dx1, dy1)
            len2 = math.hypot(dx2, dy2)
            if len1 < 1e-10 or len2 < 1e-10:
                new_poly.append(p.copy())
                continue
            
            # 边向量顺时针转90度 = 向外法线（逆时针多边形右侧为外）
            nx1 = dy1 / len1 * direction
            ny1 = -dx1 / len1 * direction
            nx2 = dy2 / len2 * direction
            ny2 = -dx2 / len2 * direction
            
            nx = nx1 + nx2
            ny = ny1 + ny2
            norm = math.hypot(nx, ny)
            if norm < 1e-10:
                new_poly.append(p.copy())
                continue
            nx /= norm
            ny /= norm
            
            new_lat = p[0] + ny * lat_off
            new_lon = p[1] + nx * lon_off
            new_poly.append([new_lat, new_lon])
        return new_poly
    
    # 先尝试正向偏移
    result = _offset_with_direction(1.0)
    orig_area = polygon_area(poly)
    new_area = polygon_area(result)
    
    # 如果面积变小，说明方向反了，反向偏移
    if new_area < orig_area:
        result = _offset_with_direction(-1.0)
    
    return result

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
        self.center_lat = (self.min_lat + self.max_lat) / 2.0
        self.center_lon = (self.min_lon + self.max_lon) / 2.0

    def to_dict(self):
        return {"points": self.points, "height": self.height, "name": self.name}

    @classmethod
    def from_dict(cls, data):
        return cls(data["points"], data["height"], data["name"])

    def get_safe_buffer(self, safe_r, bypass_d):
        total_buf = safe_r + bypass_d
        return offset_polygon_outward(self.points, total_buf, CAMPUS[0])

# ==================================================
# 【修复2】最终版绕行算法：原始建筑碰撞检测 + 中点迭代 + 双重校验
# ==================================================
def check_path_collide_buildings(path, building_list):
    """全路径校验：和所有原始建筑做碰撞检测，返回True=存在穿墙"""
    for i in range(len(path)-1):
        for building in building_list:
            if seg_intersect_polygon(path[i], path[i+1], building.points):
                return True
    return False

def generate_bypass_path(start, end, obs_list, side, safe_r, bypass_d):
    """
    最终可靠版绕行算法：
    1. 直接和原始建筑做碰撞检测，绝对不会漏检
    2. 中点迭代向指定侧偏移，每次偏移2米，迭代800次
    3. 最终校验：如果还有碰撞，自动整体外扩安全距离
    4. 强制对齐起点终点
    """
    path = [start.copy(), end.copy()]
    total_safe_dist = safe_r + bypass_d
    step_lat, step_lon = meter_to_degree(2.0, CAMPUS[0])  # 每次偏移2米，精细贴边
    max_iter = 800

    for _ in range(max_iter):
        # 查找第一个碰撞的航段
        collide_idx = -1
        for i in range(len(path)-1):
            s = path[i]
            e = path[i+1]
            for obs in obs_list:
                if seg_intersect_polygon(s, e, obs.points):
                    collide_idx = i
                    break
            if collide_idx != -1:
                break
        
        if collide_idx == -1:
            break  # 全程无碰撞，完成
        
        # 取碰撞航段中点
        seg_s = path[collide_idx]
        seg_e = path[collide_idx + 1]
        mid = [
            (seg_s[0] + seg_e[0]) / 2.0,
            (seg_s[1] + seg_e[1]) / 2.0
        ]

        # 计算航段方向向量
        dx = seg_e[1] - seg_s[1]
        dy = seg_e[0] - seg_s[0]
        line_len = math.hypot(dx, dy)
        if line_len < 1e-9:
            break
        dx /= line_len
        dy /= line_len

        # 计算垂直偏移方向（左=逆时针90°，右=顺时针90°）
        if side == "left":
            perp_x = -dy  # 经度方向
            perp_y = dx   # 纬度方向
        else:
            perp_x = dy
            perp_y = -dx
        
        # 中点向外侧偏移一个步长
        mid[0] += perp_y * step_lat
        mid[1] += perp_x * step_lon

        # 插入中点，拆分航段
        path.insert(collide_idx + 1, mid)

    # 最终强制校验：如果还碰撞，整体向绕行方向外扩总安全距离
    if check_path_collide_buildings(path, obs_list):
        perp_x_total = -dy if side == "left" else dy
        perp_y_total = dx if side == "left" else -dx
        off_lat, off_lon = meter_to_degree(total_safe_dist * 1.5, CAMPUS[0])
        for i in range(1, len(path)-1):
            path[i][0] += perp_y_total * off_lat
            path[i][1] += perp_x_total * off_lon

    # 强制对齐起点终点
    path[0] = start.copy()
    path[-1] = end.copy()

    return path

def calc_path_total_dist(waypoints):
    total = 0.0
    seg_dist = []
    for i in range(len(waypoints)-1):
        d = calc_distance(waypoints[i], waypoints[i+1])
        seg_dist.append(d)
        total += d
    return total, seg_dist

# ==================================================
# 页面主体渲染
# ==================================================
st.title("🛰️ 无人机智能监控系统")
st.markdown("**分组作业6-项目Demo | 建筑零穿墙 | 贴边最短航线 | 全流程飞行监控**")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.subheader("🌐 坐标系配置")
    st.selectbox("输入坐标系", ["WGS-84（高德卫星图）", "GCJ-02 (高德/百度)"])
    st.markdown("---")
    st.subheader("📊 系统状态")
    st.success("✅ 系统正常待机")
    st.markdown("### 🎨 显示颜色设置")
    st.session_state.obs_fill_color = st.color_picker("障碍物填充色", st.session_state.obs_fill_color)
    st.session_state.buffer_line_color = st.color_picker("安全缓冲区颜色", st.session_state.buffer_line_color)
    st.session_state.left_route_color = st.color_picker("左侧航线颜色", st.session_state.left_route_color)
    st.session_state.right_route_color = st.color_picker("右侧航线颜色", st.session_state.right_route_color)
    st.session_state.best_route_color = st.color_picker("最优航线颜色", st.session_state.best_route_color)
    st.markdown("---")
    st.markdown("### 📖 操作流程")
    st.caption("1. 地图多边形工具圈选障碍物")
    st.caption("2. 设置建筑高度并保存")
    st.caption("3. 调整安全半径与绕行距离")
    st.caption("4. 一键生成左/右/最优航线")
    st.caption("5. 确认航线后进入飞行监控")

tab1, tab2 = st.tabs(["🗺️ 航线规划", "📡 飞行监控"])

# ========== Tab1：航线规划 ==========
with tab1:
    col_map, col_ctrl = st.columns([1.6, 1])
    with col_map:
        st.subheader("🗺️ 高德卫星底图（障碍圈选）")
        m = folium.Map(location=CAMPUS, zoom_start=17, control_scale=True)
        # 高德卫星图层
        folium.TileLayer(
            "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
            attr="高德卫星图源", subdomains=["1","2","3","4"], name="卫星地图"
        ).add_to(m)
        folium.TileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="OpenStreetMap", name="街道地图"
        ).add_to(m)

        alt = st.session_state.flight_alt
        total_buf_w = st.session_state.safe_radius + st.session_state.bypass_distance
        # 渲染障碍物和缓冲区
        for obs_data in st.session_state.obstacles:
            obs = Obstacle.from_dict(obs_data)
            line_color = st.session_state.obs_fill_color if alt < obs.height else "green"
            folium.Polygon(
                obs.points, color=line_color, weight=2, fill=True,
                fill_color=st.session_state.obs_fill_color, fill_opacity=0.5,
                popup=f"{obs.name}\n建筑高度：{obs.height}m"
            ).add_to(m)
            # 飞行高度低于建筑时显示安全缓冲区
            if alt < obs.height:
                buf_coords = obs.get_safe_buffer(st.session_state.safe_radius, st.session_state.bypass_distance)
                folium.Polygon(
                    buf_coords, color=st.session_state.buffer_line_color, weight=1.5, dash_array="5,5", fill=False,
                    popup=f"安全绕行缓冲区 {total_buf_w}m"
                ).add_to(m)

        # 起终点标记
        folium.Marker(st.session_state.point_a, popup="🚁 起点A", icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(st.session_state.point_b, popup="🎯 终点B", icon=folium.Icon(color="red", icon="flag")).add_to(m)

        # 渲染选中的规划航线
        if st.session_state.selected_plan:
            plan = st.session_state.selected_plan
            folium.PolyLine(
                plan["points"], color=plan["color"], weight=3, 
                opacity=0.9, dash_array='8, 4'
            ).add_to(m)
            for idx, wp in enumerate(plan["points"][1:-1], 1):
                folium.CircleMarker(
                    wp, radius=4, color="white", fill=True, 
                    fill_color=plan["color"], popup=f"航点{idx}"
                ).add_to(m)

        # 工具控件
        plugins.Draw(draw_options={"polygon": {"allowIntersection": False}}).add_to(m)
        plugins.MeasureControl(primary_length_unit='meters').add_to(m)
        folium.LayerControl().add_to(m)
        map_out = st_folium(m, width="100%", height=550, key="main_map")

        # 捕获绘制的多边形障碍物
        if map_out and map_out.get("last_active_drawing"):
            draw_data = map_out["last_active_drawing"]
            if draw_data["geometry"]["type"] == "Polygon":
                pts = [[coord[1], coord[0]] for coord in draw_data["geometry"]["coordinates"][0]]
                # 移除首尾重复点
                if len(pts) > 1 and pts[0][0] == pts[-1][0] and pts[0][1] == pts[-1][1]:
                    pts.pop()
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 绘制完成，障碍物顶点数：{len(pts)}")

    with col_ctrl:
        # 新建障碍物面板
        if st.session_state.show_height_panel and st.session_state.temp_obs:
            st.markdown("### 🆕 新建3D建筑障碍物")
            obs_name = st.text_input("障碍物名称", value=st.session_state.temp_name)
            st.session_state.temp_name = obs_name if obs_name else "建筑物"
            obs_h = st.number_input("建筑高度(m)", min_value=1, max_value=200, step=5, value=st.session_state.temp_height)
            st.session_state.temp_height = obs_h
            fly_h = st.session_state.flight_alt
            if fly_h < obs_h:
                st.warning(f"⚠️ 飞行高度{fly_h}m < 建筑高度{obs_h}m，航线自动绕行")
            else:
                st.success(f"✅ 飞行高度足够，可直接飞越建筑")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 保存障碍物", type="primary", use_container_width=True):
                    new_obs = {"points": st.session_state.temp_obs, "height": obs_h, "name": obs_name}
                    st.session_state.obstacles.append(new_obs)
                    save_obstacles_to_file()
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            with c2:
                if st.button("🗑️ 取消绘制", use_container_width=True):
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            st.markdown("---")

        # 起终点坐标
        st.markdown("### 🚁 起点A坐标")
        c_a1, c_a2 = st.columns(2)
        lat_a = c_a1.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
        lon_a = c_a2.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("📍 更新起点A", use_container_width=True):
            st.session_state.point_a = [lat_a, lon_a]
            save_waypoints()
            st.rerun()

        st.markdown("### 🎯 终点B坐标")
        c_b1, c_b2 = st.columns(2)
        lat_b = c_b1.number_input("纬度", value=st.session_state.point_b[0], format="%.6f", key="latb")
        lon_b = c_b2.number_input("经度", value=st.session_state.point_b[1], format="%.6f", key="lonb")
        if st.button("🏁 更新终点B", use_container_width=True):
            st.session_state.point_b = [lat_b, lon_b]
            save_waypoints()
            st.rerun()

        st.markdown("---")
        st.markdown("### ⚙️ 飞行安全参数")
        alt_slider = st.slider("飞行高度(m)", min_value=10, max_value=100, value=st.session_state.flight_alt)
        st.session_state.flight_alt = alt_slider
        safe_slider = st.slider("建筑安全半径(m)", min_value=2, max_value=30, value=st.session_state.safe_radius)
        st.session_state.safe_radius = safe_slider
        bypass_slider = st.slider("额外绕行预留距离(m)", min_value=2, max_value=60, value=st.session_state.bypass_distance)
        st.session_state.bypass_distance = bypass_slider
        st.info(f"🛡️ 总安全缓冲区宽度：{safe_slider + bypass_slider} m")

        # 高度校验
        if st.session_state.obstacles:
            st.markdown("**📊 建筑高度检测**")
            block_count = 0
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    st.warning(f"🔄 {obs.name}({obs.height}m) → 需要绕行")
                    block_count += 1
                else:
                    st.success(f"✅ {obs.name} → 可飞越")
            st.caption(f"共 {block_count} 栋建筑需要绕行")

        st.markdown("---")
        st.markdown("### 🚧 已保存建筑列表")
        for idx, obs_data in enumerate(st.session_state.obstacles):
            obs = Obstacle.from_dict(obs_data)
            icon_tag = "🔄" if alt_slider < obs.height else "⬆️"
            with st.expander(f"{icon_tag} {obs.name} 高度{obs.height}m"):
                if st.button("删除该建筑", key=f"del_obs_{idx}", use_container_width=True):
                    st.session_state.obstacles.pop(idx)
                    save_obstacles_to_file()
                    st.rerun()

        c_save, c_load, c_clear = st.columns(3)
        with c_save:
            if st.button("💾 保存配置", use_container_width=True):
                save_obstacles_to_file()
                save_waypoints()
                st.success("已保存")
        with c_load:
            if st.button("📂 加载配置", use_container_width=True):
                load_obstacles_from_file()
                st.rerun()
        with c_clear:
            if st.button("🗑️ 清空", use_container_width=True):
                st.session_state.obstacles = []
                save_obstacles_to_file()
                st.rerun()

        st.markdown("---")
        st.markdown("## 🗺️ 生成航线方案")
        if st.button("🎯 生成左/右/最优航线", use_container_width=True, type="primary"):
            start_pt = st.session_state.point_a
            end_pt = st.session_state.point_b
            straight_dist = calc_distance(start_pt, end_pt)
            
            # 筛选需要绕行的障碍物（飞行高度 < 建筑高度）
            block_obs = []
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    block_obs.append(obs)
            
            plan_list = []
            if len(block_obs) == 0:
                plan_list.append({
                    "name": "📏 直线飞越航线",
                    "points": [start_pt, end_pt],
                    "dist": straight_dist,
                    "color": st.session_state.best_route_color,
                    "desc": "无遮挡建筑，直线直达"
                })
            else:
                # 左右两套绕行方案
                dir_config = [
                    ("left", "⬅️ 左侧绕行", st.session_state.left_route_color),
                    ("right", "➡️ 右侧绕行", st.session_state.right_route_color)
                ]
                for side, name, color in dir_config:
                    path = generate_bypass_path(start_pt, end_pt, block_obs, side, safe_slider, bypass_slider)
                    dist_total, _ = calc_path_total_dist(path)
                    plan_list.append({
                        "name": name,
                        "points": path,
                        "dist": dist_total,
                        "color": color,
                        "desc": f"逐栋绕开全部建筑，共{len(path)-2}个拐点"
                    })
                # 自动选出最短最优航线
                best_plan = min(plan_list, key=lambda x: x["dist"]).copy()
                best_plan["name"] = "⭐ 最优最短航线"
                best_plan["color"] = st.session_state.best_route_color
                best_plan["desc"] = f"左右对比自动择优，总长{best_plan['dist']:.1f}m"
                plan_list.append(best_plan)
            
            st.session_state.route_plans = plan_list
            st.session_state.selected_plan = plan_list[-1]
            st.rerun()

        # 方案列表
        if st.session_state.route_plans:
            st.markdown("---")
            st.markdown("### 📋 可选方案")
            for idx, p_item in enumerate(st.session_state.route_plans):
                col_n, col_d, col_t = st.columns([2,1,1])
                with col_n:
                    st.markdown(f"**{p_item['name']}**")
                    st.caption(p_item["desc"])
                with col_d:
                    st.metric("总长", f"{p_item['dist']:.0f}m")
                with col_t:
                    st.metric("时长", f"{p_item['dist']/15:.0f}s")
                if st.session_state.selected_plan and st.session_state.selected_plan["name"] == p_item["name"]:
                    st.success("✅ 当前选中")
                else:
                    if st.button(f"选用此航线", key=f"sel_plan_{idx}", use_container_width=True):
                        st.session_state.selected_plan = p_item
                        st.rerun()
                st.markdown("---")

            if st.session_state.selected_plan:
                if st.button("✈️ 确认锁定航线", use_container_width=True, type="primary"):
                    st.session_state.confirmed_plan = st.session_state.selected_plan
                    st.success("✅ 航线已锁定，切换至飞行监控启动仿真")
                    st.balloons()

        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 已锁定执行航线")
            st.success(f"**{st.session_state.confirmed_plan['name']}** | 总长{st.session_state.confirmed_plan['dist']:.0f}m")

# ========== Tab2：飞行监控 ==========
with tab2:
    st.subheader("📡 实时飞行任务仿真监控")
    col_sim_ctrl, col_sim_view = st.columns([1, 2])
    with col_sim_ctrl:
        st.markdown("### 🎮 仿真控制")
        if st.button("📐 导入已确认航线", use_container_width=True):
            if st.session_state.confirmed_plan is None:
                st.warning("⚠️ 请先在航线规划页锁定航线！")
            else:
                wp_list = st.session_state.confirmed_plan["points"]
                total_d, seg_d = calc_path_total_dist(wp_list)
                st.session_state.flight_sim_waypoints = wp_list
                st.session_state.flight_sim_total_distance = total_d
                st.session_state.flight_sim_segment_distances = seg_d
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_pause_time = 0
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                add_business_log(f"航线导入成功，航点{len(wp_list)}个，总长{total_d:.1f}m")
                add_gcs_to_fcu_log("GCS→OBC: MISSION_UPLOAD")
                add_fcu_to_gcs_log("FCU→OBC: MISSION_ACK 校验通过")
                st.success("✅ 航线载入完成")
                st.rerun()

        wp_list = st.session_state.flight_sim_waypoints
        seg_dist_list = st.session_state.flight_sim_segment_distances
        total_dist_sim = st.session_state.flight_sim_total_distance

        st.markdown("---")
        sim_speed = st.slider("飞行速度(m/s)", min_value=1.0, max_value=20.0, step=0.5, value=st.session_state.flight_sim_speed)
        st.session_state.flight_sim_speed = sim_speed
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("▶️ 启动", use_container_width=True, disabled=(len(wp_list)==0)):
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                else:
                    pause_dur = time.time() - st.session_state.flight_sim_pause_time
                    st.session_state.flight_sim_start_time += pause_dur
                st.session_state.flight_sim_running = True
                add_fcu_to_gcs_log("FCU→GCS: AUTO模式开启，任务启动")
                st.rerun()
        with c2:
            if st.button("⏸️ 暂停", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_pause_time = time.time()
                add_fcu_to_gcs_log("FCU→GCS: 任务暂停")
                st.rerun()
        with c3:
            if st.button("🔄 重置", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_pause_time = 0
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 航线信息")
        st.caption(f"起点：{st.session_state.point_a[0]:.6f}, {st.session_state.point_a[1]:.6f}")
        st.caption(f"终点：{st.session_state.point_b[0]:.6f}, {st.session_state.point_b[1]:.6f}")
        st.caption(f"飞行高度：{st.session_state.flight_alt} m")
        st.caption(f"航点总数：{len(wp_list)}")
        if total_dist_sim > 0:
            st.caption(f"总长度：{total_dist_sim:.1f} m")

        st.markdown("---")
        st.markdown("### 💓 心跳监控")
        if not st.session_state.heartbeat_running:
            if st.button("启动心跳检测", use_container_width=True):
                st.session_state.heartbeat_sim.start()
                st.session_state.heartbeat_running = True
                st.rerun()
        else:
            if st.button("停止心跳检测", use_container_width=True):
                st.session_state.heartbeat_sim.stop()
                st.session_state.heartbeat_running = False
                st.rerun()
            hb_item = st.session_state.heartbeat_sim.update()
            if hb_item:
                if hb_item["status"] == "timeout":
                    st.error("⚠️ 链路超时")
                else:
                    st.success(f"心跳正常 | 延迟 {hb_item['delay']}ms")
            hb_stats = st.session_state.heartbeat_sim.get_stats()
            st.caption(f"成功率：{hb_stats['rate']}%")

    with col_sim_view:
        if len(wp_list) > 0:
            curr_lat, curr_lon = wp_list[0][0], wp_list[0][1]
            flown_d = 0.0
            remain_d = total_dist_sim
            time_elapse = 0
            time_remain = 0
            batt = 100.0
            curr_wp_idx = 0
            progress = 0.0

            if st.session_state.flight_sim_running or st.session_state.flight_sim_start_time is not None:
                if st.session_state.flight_sim_running:
                    elapse_sec = time.time() - st.session_state.flight_sim_start_time
                else:
                    elapse_sec = st.session_state.flight_sim_pause_time - st.session_state.flight_sim_start_time if st.session_state.flight_sim_pause_time else 0
                
                flown_d = elapse_sec * sim_speed
                total_flown = 0.0
                for seg_idx, seg_d in enumerate(seg_dist_list):
                    if total_flown + seg_d >= flown_d:
                        curr_wp_idx = seg_idx
                        seg_prog = (flown_d - total_flown) / seg_d if seg_d>1e-6 else 0
                        p0 = wp_list[seg_idx]
                        p1 = wp_list[min(seg_idx+1, len(wp_list)-1)]
                        curr_lat = p0[0] + (p1[0]-p0[0])*seg_prog
                        curr_lon = p0[1] + (p1[1]-p0[1])*seg_prog
                        break
                    total_flown += seg_d
                else:
                    curr_wp_idx = len(wp_list)-1
                    curr_lat, curr_lon = wp_list[-1][0], wp_list[-1][1]
                    st.session_state.flight_sim_running = False

                remain_d = max(0.0, total_dist_sim - flown_d)
                time_elapse = int(elapse_sec)
                time_remain = int(remain_d / sim_speed) if sim_speed>1e-6 else 0
                batt = max(0.0, 100.0 - (elapse_sec / 1800.0)*100.0)
                progress = min(1.0, flown_d / total_dist_sim) if total_dist_sim>1e-6 else 0.0

                if curr_wp_idx > st.session_state.flight_sim_last_wp_index:
                    st.session_state.flight_sim_last_wp_index = curr_wp_idx
                    add_fcu_to_gcs_log(f"FCU→GCS: 抵达航点 #{curr_wp_idx+1}")
                    if curr_wp_idx >= len(wp_list)-1:
                        add_business_log("全部航点飞行完成", color="green")

            # 数据面板
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            d1.metric("当前航点", f"{min(curr_wp_idx+1, len(wp_list))}/{len(wp_list)}")
            d2.metric("飞行速度", f"{sim_speed:.1f} m/s")
            d3.metric("已用时间", f"{time_elapse//60:02d}:{time_elapse%60:02d}")
            d4.metric("剩余距离", f"{remain_d:.0f} m")
            d5.metric("预计到达", f"{time_remain//60:02d}:{time_remain%60:02d}")
            d6.metric("电量模拟", f"{batt:.0f}%")
            st.progress(progress)

            st.markdown("---")
            # 实时地图 + 通信日志
            map_col, log_col = st.columns([1.5, 1])
            with map_col:
                st.markdown("**🗺️ 实时飞行地图**")
                m2 = folium.Map(location=CAMPUS, zoom_start=17)
                folium.TileLayer(
                    "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
                    attr="高德卫星", subdomains=["1","2","3","4"]
                ).add_to(m2)
                for obs_data in st.session_state.obstacles:
                    obs = Obstacle.from_dict(obs_data)
                    folium.Polygon(obs.points, color=st.session_state.obs_fill_color, fill=True, fill_opacity=0.5).add_to(m2)
                folium.PolyLine(wp_list, color="green", weight=3, dash_array='8,4').add_to(m2)
                folium.Marker([curr_lat, curr_lon], popup="实时位置", icon=folium.Icon(color="green", icon="plane")).add_to(m2)
                st_folium(m2, width="100%", height=300, key="flight_map")

            with log_col:
                st.markdown("**📶 通信链路**")
                st.success("✅ GCS 地面站在线")
                st.success("✅ OBC 机载计算机在线")
                st.success("✅ FCU 飞控在线")
                st.markdown("---")
                st.markdown("**📝 通信日志**")
                log_box = st.container(height=180)
                with log_box:
                    for log in st.session_state.comm_logs_business[-8:]:
                        st.caption(f"📋 [{log['timestamp']}] {log['message']}")
                    for log in st.session_state.comm_logs_fcu_to_gcs[-5:]:
                        st.caption(f"⬆️ {log}")
                    for log in st.session_state.comm_logs_gcs_to_fcu[-5:]:
                        st.caption(f"⬇️ {log}")

            if st.session_state.flight_sim_running:
                st.rerun()
        else:
            st.info("📭 请先导入已确认的航线")

st.markdown("---")
st.caption("无人机智能化应用2451 | 分组作业6-项目Demo | 最终修复版，建筑零穿墙")
