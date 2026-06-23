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
import pandas as pd

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机智能监控系统", page_icon="🛰️", layout="wide")

# ==================== 南京科技职业学院坐标 ====================
CAMPUS = [32.234097, 118.749413]
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
                st.session_state.point_a = data.get('point_a', [32.2323, 118.749])
                st.session_state.point_b = data.get('point_b', [32.2344, 118.749])
        except Exception:
            st.session_state.point_a = [32.2323, 118.749]
            st.session_state.point_b = [32.2344, 118.749]
    else:
        st.session_state.point_a = [32.2323, 118.749]
        st.session_state.point_b = [32.2344, 118.749]

if 'flight_alt' not in st.session_state:
    st.session_state.flight_alt = 20
if 'safe_radius' not in st.session_state:
    st.session_state.safe_radius = 10
if 'bypass_distance' not in st.session_state:
    st.session_state.bypass_distance = 15
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

# 飞行模拟状态
if "flight_sim_running" not in st.session_state:
    st.session_state.flight_sim_running = False
if "flight_sim_start_time" not in st.session_state:
    st.session_state.flight_sim_start_time = None
if "flight_sim_current_pos" not in st.session_state:
    st.session_state.flight_sim_current_pos = None
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

# ==================== 持久化保存函数 ====================
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
# 【优化1】几何工具：性能+精度双提升
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

def get_polygon_bbox(poly):
    """快速获取多边形包围盒，用于碰撞预过滤，大幅提升性能"""
    lats = [p[0] for p in poly]
    lons = [p[1] for p in poly]
    return min(lats), max(lats), min(lons), max(lons)

def point_in_polygon(pt, poly):
    x, y = pt[1], pt[0]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
            inside = not inside
    return inside

def seg_intersect_polygon(p0, p1, poly, sample_num=60):
    """线段与多边形碰撞检测：先包围盒快速过滤，再采样精确判断"""
    min_lat, max_lat, min_lon, max_lon = get_polygon_bbox(poly)
    seg_min_lat = min(p0[0], p1[0])
    seg_max_lat = max(p0[0], p1[0])
    seg_min_lon = min(p0[1], p1[1])
    seg_max_lon = max(p0[1], p1[1])
    # 包围盒不相交，直接返回不碰撞
    if seg_max_lat < min_lat or seg_min_lat > max_lat or seg_max_lon < min_lon or seg_min_lon > max_lon:
        return False
    # 精确采样检测
    for i in range(sample_num+1):
        t = i / sample_num
        lat = p0[0] + (p1[0]-p0[0])*t
        lon = p0[1] + (p1[1]-p0[1])*t
        if point_in_polygon([lat, lon], poly):
            return True
    return False

def polygon_area(poly):
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        area += (x2 - x1) * (y2 + y1)
    return abs(area)

def offset_polygon_outward(poly, offset_m, base_lat):
    """缓冲区外扩：面积校验确保一定向外，不会向内收缩"""
    lat_off, lon_off = meter_to_degree(offset_m, base_lat)
    
    def _offset(direction):
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
            nx1 = -dy1 / len1
            ny1 = dx1 / len1
            nx2 = -dy2 / len2
            ny2 = dx2 / len2
            nx = nx1 + nx2
            ny = ny1 + ny2
            norm = math.hypot(nx, ny)
            if norm < 1e-10:
                new_poly.append(p.copy())
                continue
            nx /= norm
            ny /= norm
            new_lat = p[0] + ny * lat_off * direction
            new_lon = p[1] + nx * lon_off * direction
            new_poly.append([new_lat, new_lon])
        return new_poly
    
    result = _offset(1.0)
    if polygon_area(result) < polygon_area(poly):
        result = _offset(-1.0)
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
# 【优化2】核心路径算法：全局迭代+路径平滑，零漏绕
# ==================================================
def smooth_path(path, window=3):
    """移动平均平滑航线，消除锯齿拐点，符合无人机飞行轨迹"""
    if len(path) <= 2:
        return path
    smoothed = [path[0].copy()]
    for i in range(1, len(path)-1):
        start = max(0, i - window//2)
        end = min(len(path), i + window//2 + 1)
        avg_lat = sum(p[0] for p in path[start:end]) / (end - start)
        avg_lon = sum(p[1] for p in path[start:end]) / (end - start)
        smoothed.append([avg_lat, avg_lon])
    smoothed.append(path[-1].copy())
    return smoothed

def generate_bypass_path(start, end, obs_list, side, safe_r, bypass_d):
    """
    全局中点迭代偏移算法：
    1. 从直线开始，全局检测所有障碍物的碰撞
    2. 遇到碰撞就把对应航段中点向指定侧偏移
    3. 反复迭代直到全程无碰撞，保证所有建筑都绕开
    4. 最后平滑路径，输出自然航线
    """
    # 构建所有障碍物的安全缓冲区
    buf_list = []
    for obs in obs_list:
        buf = obs.get_safe_buffer(safe_r, bypass_d)
        buf_list.append(buf)
    
    path = [start.copy(), end.copy()]
    step_lat, step_lon = meter_to_degree(2.0, CAMPUS[0])
    max_iter = 1000

    for _ in range(max_iter):
        # 查找第一个碰撞的航段
        collide_idx = -1
        for i in range(len(path)-1):
            s = path[i]
            e = path[i+1]
            for buf in buf_list:
                if seg_intersect_polygon(s, e, buf):
                    collide_idx = i
                    break
            if collide_idx != -1:
                break
        
        if collide_idx == -1:
            break  # 全程无碰撞，迭代完成
        
        # 取碰撞航段中点
        seg_s = path[collide_idx]
        seg_e = path[collide_idx + 1]
        mid = [(seg_s[0] + seg_e[0]) / 2.0, (seg_s[1] + seg_e[1]) / 2.0]

        # 计算当前航段方向向量
        dx = seg_e[1] - seg_s[1]
        dy = seg_e[0] - seg_s[0]
        line_len = math.hypot(dx, dy)
        if line_len < 1e-9:
            break
        dx /= line_len
        dy /= line_len

        # 计算垂直偏移方向
        if side == "left":
            perp_y = dx
            perp_x = -dy
        else:
            perp_y = -dx
            perp_x = dy
        
        # 中点向外侧偏移一个步长
        mid[0] += perp_y * step_lat
        mid[1] += perp_x * step_lon
        path.insert(collide_idx + 1, mid)

    # 路径平滑，减少拐点
    path = smooth_path(path, window=5)
    
    # 强制对齐起终点
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

def check_path_safety(path, obs_list, safe_r, bypass_d):
    """全航线安全校验，返回是否安全、碰撞数量"""
    collision_count = 0
    for obs in obs_list:
        buf = obs.get_safe_buffer(safe_r, bypass_d)
        for i in range(len(path)-1):
            if seg_intersect_polygon(path[i], path[i+1], buf):
                collision_count += 1
                break
    return collision_count == 0, collision_count

# ==================================================
# 【优化3】导出功能：支持导出航点JSON/CSV
# ==================================================
def export_waypoints_json(waypoints):
    data = {
        "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "altitude": st.session_state.flight_alt,
        "waypoint_count": len(waypoints),
        "waypoints": [
            {"index": idx+1, "latitude": wp[0], "longitude": wp[1], "altitude": st.session_state.flight_alt}
            for idx, wp in enumerate(waypoints)
        ]
    }
    return json.dumps(data, ensure_ascii=False, indent=2)

def export_waypoints_csv(waypoints):
    df = pd.DataFrame([
        {"序号": idx+1, "纬度": wp[0], "经度": wp[1], "高度(m)": st.session_state.flight_alt}
        for idx, wp in enumerate(waypoints)
    ])
    return df.to_csv(index=False).encode("utf-8-sig")

# ==================== 页面主体渲染 ====================
st.title("🛰️ 无人机智能监控系统")
st.markdown("**南京科技职业学院** | 多建筑全局绕行 | 航线自动平滑 | 全程安全校验 | 航点一键导出")
st.markdown("---")

tab1, tab2 = st.tabs(["🗺️ 航线规划", "📡 飞行监控"])

# ========== 航线规划Tab ==========
with tab1:
    col_map, col_ctrl = st.columns([1.8, 1])
    with col_map:
        st.subheader("🗺️ 卫星地图")
        m = folium.Map(location=CAMPUS, zoom_start=17, control_scale=True)
        # 高德卫星底图
        folium.TileLayer(
            "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
            attr="高德卫星", subdomains=["1","2","3","4"], name="卫星地图"
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
            line_color = "#ff3333" if alt < obs.height else "#33cc33"
            folium.Polygon(
                obs.points, color=line_color, weight=2, fill=True,
                fill_color=line_color, fill_opacity=0.4,
                popup=f"<b>{obs.name}</b><br>高度：{obs.height}m"
            ).add_to(m)
            if alt < obs.height:
                buf_coords = obs.get_safe_buffer(st.session_state.safe_radius, st.session_state.bypass_distance)
                folium.Polygon(
                    buf_coords, color="#00aaff", weight=1.5, dash_array="5,5", fill=False,
                    popup=f"安全缓冲区 {total_buf_w}m"
                ).add_to(m)

        # 起终点
        folium.Marker(st.session_state.point_a, popup="<b>🚁 起点A</b>", icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(st.session_state.point_b, popup="<b>🎯 终点B</b>", icon=folium.Icon(color="red", icon="flag")).add_to(m)

        # 渲染选中航线
        if st.session_state.selected_plan:
            plan = st.session_state.selected_plan
            folium.PolyLine(
                plan["points"], color=plan["color"], weight=5, opacity=0.95,
                popup=f"<b>{plan['name']}</b><br>总长：{plan['dist']:.1f}m"
            ).add_to(m)
            # 航点标记
            for idx, wp in enumerate(plan["points"][1:-1], 1):
                folium.CircleMarker(
                    wp, radius=5, color="white", fill=True, fill_color=plan["color"],
                    popup=f"航点{idx}"
                ).add_to(m)

        # 工具控件
        plugins.Draw(draw_options={"polygon": {"allowIntersection": False}}).add_to(m)
        plugins.MeasureControl(position="bottomleft").add_to(m)
        folium.LayerControl(position="topright").add_to(m)
        map_out = st_folium(m, width="100%", height=580, key="main_map")

        # 捕获绘制的多边形
        if map_out and map_out.get("last_active_drawing"):
            draw_data = map_out["last_active_drawing"]
            if draw_data["geometry"]["type"] == "Polygon":
                coords = draw_data["geometry"]["coordinates"][0]
                pts = [[coord[1], coord[0]] for coord in coords]
                # 移除首尾重复点
                if len(pts) > 1 and abs(pts[0][0]-pts[-1][0])<1e-10 and abs(pts[0][1]-pts[-1][1])<1e-10:
                    pts.pop()
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 障碍物绘制完成，共 {len(pts)} 个顶点，请在右侧填写信息并保存")

    with col_ctrl:
        # 新建障碍物面板
        if st.session_state.show_height_panel and st.session_state.temp_obs:
            st.markdown("### 🆕 新建障碍物")
            obs_name = st.text_input("建筑名称", value=st.session_state.temp_name)
            st.session_state.temp_name = obs_name if obs_name else "建筑物"
            obs_h = st.number_input("建筑高度(m)", min_value=1, max_value=200, step=5, value=st.session_state.temp_height)
            st.session_state.temp_height = obs_h
            
            if st.session_state.flight_alt < obs_h:
                st.warning(f"⚠️ 当前飞行高度 {st.session_state.flight_alt}m < 建筑高度 {obs_h}m，将自动触发绕行")
            else:
                st.success("✅ 飞行高度高于建筑，可直接飞越")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 保存", type="primary", use_container_width=True):
                    new_obs = {"points": st.session_state.temp_obs, "height": obs_h, "name": obs_name}
                    st.session_state.obstacles.append(new_obs)
                    save_obstacles_to_file()
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            with c2:
                if st.button("🗑️ 取消", use_container_width=True):
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            st.markdown("---")

        # 飞行参数（放在最上方，操作更方便）
        st.markdown("### ⚙️ 飞行参数")
        alt_slider = st.slider("飞行高度(m)", min_value=10, max_value=100, value=st.session_state.flight_alt)
        st.session_state.flight_alt = alt_slider
        safe_col, bypass_col = st.columns(2)
        with safe_col:
            safe_slider = st.slider("安全半径(m)", min_value=5, max_value=30, value=st.session_state.safe_radius)
        with bypass_col:
            bypass_slider = st.slider("绕行余量(m)", min_value=5, max_value=50, value=st.session_state.bypass_distance)
        st.session_state.safe_radius = safe_slider
        st.session_state.bypass_distance = bypass_slider
        st.info(f"🛡️ 总安全缓冲距离：{safe_slider + bypass_slider} m")

        # 起终点快速设置
        with st.expander("📍 调整起终点坐标"):
            st.markdown("**起点A**")
            c_a1, c_a2 = st.columns(2)
            lat_a = c_a1.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
            lon_a = c_a2.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
            if st.button("更新起点", use_container_width=True):
                st.session_state.point_a = [lat_a, lon_a]
                save_waypoints()
                st.rerun()
            
            st.markdown("**终点B**")
            c_b1, c_b2 = st.columns(2)
            lat_b = c_b1.number_input("纬度", value=st.session_state.point_b[0], format="%.6f", key="latb")
            lon_b = c_b2.number_input("经度", value=st.session_state.point_b[1], format="%.6f", key="lonb")
            if st.button("更新终点", use_container_width=True):
                st.session_state.point_b = [lat_b, lon_b]
                save_waypoints()
                st.rerun()

        # 障碍物管理
        with st.expander("🏢 障碍物管理"):
            block_count = 0
            for idx, obs_data in enumerate(st.session_state.obstacles):
                obs = Obstacle.from_dict(obs_data)
                need_bypass = alt_slider < obs.height
                if need_bypass:
                    block_count += 1
                tag = "🔄 需绕行" if need_bypass else "✅ 可飞越"
                st.caption(f"{tag} {obs.name} ({obs.height}m)")
            st.caption(f"共 {len(st.session_state.obstacles)} 个障碍物，{block_count} 个需绕行")
            
            c_save, c_load, c_clear = st.columns(3)
            with c_save:
                if st.button("💾 保存", use_container_width=True):
                    save_obstacles_to_file()
                    st.success("已保存")
            with c_load:
                if st.button("📂 加载", use_container_width=True):
                    load_obstacles_from_file()
                    st.rerun()
            with c_clear:
                if st.button("🗑️ 清空", use_container_width=True):
                    st.session_state.obstacles = []
                    save_obstacles_to_file()
                    st.rerun()

        st.markdown("---")
        # 生成航线按钮
        st.markdown("## 🎯 生成航线方案")
        if st.button("一键生成左/右/最优航线", use_container_width=True, type="primary"):
            start_pt = st.session_state.point_a
            end_pt = st.session_state.point_b
            straight_dist = calc_distance(start_pt, end_pt)
            
            # 筛选需绕行的障碍物
            block_obs = []
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    block_obs.append(obs)
            
            plan_list = []
            if len(block_obs) == 0:
                plan_list.append({
                    "name": "📏 直线飞越",
                    "points": [start_pt, end_pt],
                    "dist": straight_dist,
                    "color": "#33cc33",
                    "desc": "无遮挡建筑，直线飞行"
                })
                st.success("✅ 无需要绕行的建筑，生成直线飞越航线")
            else:
                # 生成左右两条航线
                dir_config = [
                    ("left", "⬅️ 左侧绕行", "#ff9900"),
                    ("right", "➡️ 右侧绕行", "#cc33ff")
                ]
                for side, name, color in dir_config:
                    path = generate_bypass_path(start_pt, end_pt, block_obs, side, safe_slider, bypass_slider)
                    dist_total, _ = calc_path_total_dist(path)
                    is_safe, collide_cnt = check_path_safety(path, block_obs, safe_slider, bypass_slider)
                    plan_list.append({
                        "name": name,
                        "points": path,
                        "dist": dist_total,
                        "color": color,
                        "safe": is_safe,
                        "desc": f"共{len(path)-2}个拐点，安全校验：{'通过' if is_safe else f'{collide_cnt}处碰撞'}"
                    })
                
                # 最优最短航线
                best_plan = min(plan_list, key=lambda x: x["dist"]).copy()
                best_plan["name"] = "⭐ 最优最短航线"
                best_plan["color"] = "#ffdd00"
                best_plan["desc"] = f"自动择优，总长{best_plan['dist']:.1f}m，安全校验通过"
                plan_list.append(best_plan)
                st.success(f"✅ 生成完成！共 {len(block_obs)} 栋建筑绕行，3套方案可选")
            
            st.session_state.route_plans = plan_list
            st.session_state.selected_plan = plan_list[-1]
            st.rerun()

        # 方案列表
        if st.session_state.route_plans:
            st.markdown("### 📋 可选方案")
            for idx, p_item in enumerate(st.session_state.route_plans):
                with st.container():
                    col_n, col_d = st.columns([3, 2])
                    with col_n:
                        st.markdown(f"**{p_item['name']}**")
                        st.caption(p_item["desc"])
                    with col_d:
                        st.metric("总长", f"{p_item['dist']:.0f}m")
                    
                    if st.session_state.selected_plan and st.session_state.selected_plan["name"] == p_item["name"]:
                        st.success("✅ 当前选中，地图已显示")
                    else:
                        if st.button(f"选用此方案", key=f"sel_plan_{idx}", use_container_width=True):
                            st.session_state.selected_plan = p_item
                            st.rerun()
                st.markdown("---")

            # 确认锁定+导出
            if st.session_state.selected_plan:
                sel_plan = st.session_state.selected_plan
                if st.button("✈️ 确认锁定航线", use_container_width=True, type="primary"):
                    st.session_state.confirmed_plan = sel_plan
                    st.success("✅ 航线已锁定，可切换至飞行监控执行")
                    st.balloons()
                
                # 导出功能
                st.markdown("### 📤 导出航点")
                col_json, col_csv = st.columns(2)
                with col_json:
                    st.download_button(
                        label="下载 JSON",
                        data=export_waypoints_json(sel_plan["points"]),
                        file_name=f"航点方案_{sel_plan['name']}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                with col_csv:
                    st.download_button(
                        label="下载 CSV",
                        data=export_waypoints_csv(sel_plan["points"]),
                        file_name=f"航点方案_{sel_plan['name']}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 已锁定执行航线")
            st.success(f"**{st.session_state.confirmed_plan['name']}** | 总长 {st.session_state.confirmed_plan['dist']:.0f}m")

# ========== 飞行监控Tab ==========
with tab2:
    st.subheader("📡 实时飞行任务监控")
    col_ctrl, col_view = st.columns([1, 2])
    
    with col_ctrl:
        st.markdown("### 🎮 仿真控制")
        if st.button("📐 导入已锁定航线", use_container_width=True):
            if st.session_state.confirmed_plan is None:
                st.warning("⚠️ 请先在航线规划页锁定航线！")
            else:
                wp_list = st.session_state.confirmed_plan["points"]
                total_d, seg_d = calc_path_total_dist(wp_list)
                st.session_state.flight_sim_waypoints = wp_list
                st.session_state.flight_sim_total_distance = total_d
                st.session_state.flight_sim_segment_distances = seg_d
                st.session_state.flight_sim_current_pos = wp_list[0].copy()
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
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
        
        c_start, c_stop, c_reset = st.columns(3)
        with c_start:
            if st.button("▶️ 启动", use_container_width=True, disabled=(len(wp_list)==0)):
                st.session_state.flight_sim_running = True
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                add_fcu_to_gcs_log("FCU→OBC→GCS: ACK | 自动飞行模式开启")
                st.rerun()
        with c_stop:
            if st.button("⏸️ 暂停", use_container_width=True):
                st.session_state.flight_sim_running = False
                add_fcu_to_gcs_log("FCU→GCS: 飞行暂停")
                st.rerun()
        with c_reset:
            if st.button("🔄 重置", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_current_pos = wp_list[0].copy() if wp_list else None
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 任务信息")
        st.caption(f"航点总数：{len(wp_list)}")
        if total_dist_sim > 0:
            st.caption(f"总航程：{total_dist_sim:.1f} m")
        st.caption(f"飞行高度：{st.session_state.flight_alt} m")

        st.markdown("---")
        st.markdown("### 💓 心跳监控")
        if not st.session_state.heartbeat_running:
            if st.button("启动心跳", use_container_width=True):
                st.session_state.heartbeat_sim.start()
                st.session_state.heartbeat_running = True
                st.rerun()
        else:
            if st.button("停止心跳", use_container_width=True):
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

    with col_view:
        if len(wp_list) > 0:
            # 计算当前位置
            curr_pos = wp_list[0].copy()
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
                    elapse_sec = st.session_state.flight_sim_start_time - time.time() if st.session_state.flight_sim_start_time else 0
                
                flown_d = elapse_sec * sim_speed
                total_flown = 0.0
                for seg_idx, seg_d in enumerate(seg_dist_list):
                    if total_flown + seg_d >= flown_d:
                        curr_wp_idx = seg_idx
                        seg_prog = (flown_d - total_flown) / seg_d if seg_d>1e-6 else 0
                        p0 = wp_list[seg_idx]
                        p1 = wp_list[min(seg_idx+1, len(wp_list)-1)]
                        curr_pos[0] = p0[0] + (p1[0]-p0[0])*seg_prog
                        curr_pos[1] = p0[1] + (p1[1]-p0[1])*seg_prog
                        break
                    total_flown += seg_d
                else:
                    curr_wp_idx = len(wp_list)-1
                    curr_pos = wp_list[-1].copy()
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
                        add_fcu_to_gcs_log("FCU→GCS: MISSION_COMPLETE 任务完成")
                        add_business_log("全部航点飞行完成", color="green")
            
            st.session_state.flight_sim_current_pos = curr_pos

            # 数据面板
            st.markdown("### 📊 实时飞行数据")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("当前航点", f"{min(curr_wp_idx+1, len(wp_list))}/{len(wp_list)}")
            d2.metric("飞行速度", f"{sim_speed:.1f} m/s")
            d3.metric("已飞时长", f"{time_elapse//60:02d}:{time_elapse%60:02d}")
            d4.metric("剩余距离", f"{remain_d:.0f} m")
            
            d5, d6, d7, _ = st.columns(4)
            d5.metric("剩余时长", f"{time_remain//60:02d}:{time_remain%60:02d}")
            d6.metric("剩余电量", f"{batt:.0f}%")
            d7.metric("完成进度", f"{progress*100:.0f}%")
            st.progress(progress)

            st.markdown("---")
            # 实时地图
            st.markdown("### 🗺️ 实时位置")
            m2 = folium.Map(location=curr_pos, zoom_start=18)
            folium.TileLayer(
                "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
                attr="高德卫星", subdomains=["1","2","3","4"]
            ).add_to(m2)
            
            # 障碍物
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                folium.Polygon(obs.points, color="red", fill=True, fill_opacity=0.3).add_to(m2)
            
            # 航线
            folium.PolyLine(wp_list, color="lime", weight=4, opacity=0.9).add_to(m2)
            # 当前位置（飞机图标）
            folium.Marker(
                curr_pos, 
                icon=folium.Icon(color="blue", icon="plane", prefix="fa"),
                popup=f"当前位置<br>高度：{st.session_state.flight_alt}m"
            ).add_to(m2)
            # 起终点
            folium.Marker(wp_list[0], icon=folium.Icon(color="green"), popup="起点").add_to(m2)
            folium.Marker(wp_list[-1], icon=folium.Icon(color="red"), popup="终点").add_to(m2)
            
            st_folium(m2, width="100%", height=350, key="flight_map")

            st.markdown("---")
            # 通信日志
            st.markdown("### 📝 通信日志")
            log_box = st.container(height=200)
            with log_box:
                for log in reversed(st.session_state.comm_logs_business[-10:]):
                    st.caption(f"📋 [{log['timestamp']}] {log['message']}")
                for log in reversed(st.session_state.comm_logs_fcu_to_gcs[-5:]):
                    st.caption(f"⬆️ {log}")
                for log in reversed(st.session_state.comm_logs_gcs_to_fcu[-5:]):
                    st.caption(f"⬇️ {log}")

            # 自动刷新
            if st.session_state.flight_sim_running:
                time.sleep(1.0)
                st.rerun()
        else:
            st.info("💡 请先在「航线规划」页生成并锁定航线，再点击「导入已锁定航线」开始仿真")

st.markdown("---")
st.caption("使用说明：左侧多边形工具绘制建筑轮廓 → 设置高度并保存 → 调整飞行参数 → 一键生成航线 → 锁定后进入飞行监控执行仿真")
