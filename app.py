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

# ==================== 南京科技职业学院中心基准坐标 ====================
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
        # 默认预设4栋纵向排列建筑，匹配参考图效果
        st.session_state.obstacles = [
            {"name": "1号教学楼", "height": 35, "points": [[32.2340, 118.7487], [32.2345, 118.7487], [32.2345, 118.7503], [32.2340, 118.7503]]},
            {"name": "2号教学楼", "height": 32, "points": [[32.2332, 118.7489], [32.2337, 118.7489], [32.2337, 118.7501], [32.2332, 118.7501]]},
            {"name": "3号实训楼", "height": 38, "points": [[32.2324, 118.7488], [32.2329, 118.7488], [32.2329, 118.7502], [32.2324, 118.7502]]},
            {"name": "4号行政楼", "height": 40, "points": [[32.2315, 118.7486], [32.2321, 118.7486], [32.2321, 118.7500], [32.2315, 118.7500]]}
        ]

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
        st.session_state.point_a = [32.2347, 118.7490]  # 下方起点
        st.session_state.point_b = [32.2312, 118.7492]  # 上方终点

if 'flight_alt' not in st.session_state:
    st.session_state.flight_alt = 20
if 'safe_radius' not in st.session_state:
    st.session_state.safe_radius = 8
if 'bypass_distance' not in st.session_state:
    st.session_state.bypass_distance = 12
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

# ==================== 持久化保存函数（障碍记忆功能） ====================
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

# ==================== 心跳链路模拟器 ====================
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
# 核心几何计算（精确版，无穿墙）
# ==================================================
def calc_distance(p1, p2):
    """Haversine公式计算WGS84两点距离，单位：米"""
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    R = 6371000
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def meter_to_degree(meter, base_lat):
    """米转经纬度偏移量"""
    lat_per_m = 1.0 / 111320.0
    lon_per_m = 1.0 / (111320.0 * math.cos(math.radians(base_lat)))
    return meter * lat_per_m, meter * lon_per_m

def point_in_polygon(pt, poly):
    """射线法判断点是否在多边形内"""
    x, y = pt[1], pt[0]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
            inside = not inside
    return inside

def _ccw(A, B, C):
    return (C[0]-A[0])*(B[1]-A[1]) > (B[0]-A[0])*(C[1]-A[1])

def seg_intersect_seg(a1, a2, b1, b2):
    """精确判断两条线段是否相交"""
    return _ccw(a1, b1, b2) != _ccw(a2, b1, b2) and _ccw(a1, a2, b1) != _ccw(a1, a2, b2)

def seg_intersect_polygon(p0, p1, poly):
    """精确判断线段与多边形是否相交（端点在内或与任意边相交）"""
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
    """判断多边形环绕方向：True=逆时针，False=顺时针"""
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        area += (x2 - x1) * (y2 + y1)
    return area > 0

def offset_polygon_outward(poly, offset_m, base_lat):
    """修复版：多边形向外外扩指定米数，自动修正环绕方向"""
    lat_off, lon_off = meter_to_degree(offset_m, base_lat)
    is_ccw = polygon_winding(poly)
    direction = 1.0 if is_ccw else -1.0
    
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
        
        nx1 = -dy1 / len1 * direction
        ny1 = dx1 / len1 * direction
        nx2 = -dy2 / len2 * direction
        ny2 = dx2 / len2 * direction
        
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
# 多障碍物连续绕行核心算法（沿建筑外侧自然绕路）
# ==================================================
def find_first_collision(path, buf_list):
    """找到路径中第一个碰撞的航段和缓冲区索引"""
    for i in range(len(path)-1):
        seg_start = path[i]
        seg_end = path[i+1]
        for buf_idx, buf in enumerate(buf_list):
            if seg_intersect_polygon(seg_start, seg_end, buf):
                return i, buf_idx
    return -1, -1

def generate_bypass_path(start, end, obs_list, buf_list, side, safe_r, bypass_d):
    """
    迭代式多障碍物绕行算法：
    1. 从直线路径开始，反复找到第一个碰撞点
    2. 插入3个绕行拐点，形成沿建筑外侧的平滑走廊
    3. 迭代校验直到全程无碰撞，保证不穿墙
    """
    path = [start.copy(), end.copy()]
    total_buf = safe_r + bypass_d
    lat_off_deg, lon_off_deg = meter_to_degree(total_buf * 4.0, CAMPUS[0])
    max_iter = 80
    
    for _ in range(max_iter):
        seg_idx, buf_idx = find_first_collision(path, buf_list)
        if seg_idx == -1:
            break
        
        obs = obs_list[buf_idx]
        buf = buf_list[buf_idx]
        seg_s = path[seg_idx]
        seg_e = path[seg_idx+1]
        
        # 计算航线方向与垂直偏移方向
        dx = seg_e[1] - seg_s[1]
        dy = seg_e[0] - seg_s[0]
        line_len = math.hypot(dx, dy)
        if line_len < 1e-9:
            break
        dx /= line_len
        dy /= line_len
        
        if side == "left":
            perp_lat = -dx
            perp_lon = dy
        else:
            perp_lat = dx
            perp_lon = -dy
        
        # 生成3个绕行点，形成自然的外侧绕行走廊
        bypass_in = [
            seg_s[0] + perp_lat * lat_off_deg * 1.1,
            seg_s[1] + perp_lon * lon_off_deg * 1.1
        ]
        bypass_mid = [
            obs.center_lat + perp_lat * lat_off_deg * 2.0,
            obs.center_lon + perp_lon * lon_off_deg * 2.0
        ]
        bypass_out = [
            seg_e[0] + perp_lat * lat_off_deg * 1.1,
            seg_e[1] + perp_lon * lon_off_deg * 1.1
        ]
        
        # 迭代外扩直到完全不碰撞
        expand_step = 1.3
        for __ in range(30):
            ok1 = not seg_intersect_polygon(seg_s, bypass_in, buf)
            ok2 = not seg_intersect_polygon(bypass_in, bypass_mid, buf)
            ok3 = not seg_intersect_polygon(bypass_mid, bypass_out, buf)
            ok4 = not seg_intersect_polygon(bypass_out, seg_e, buf)
            if ok1 and ok2 and ok3 and ok4:
                break
            bypass_in[0] += perp_lat * lat_off_deg * expand_step
            bypass_in[1] += perp_lon * lon_off_deg * expand_step
            bypass_mid[0] += perp_lat * lat_off_deg * expand_step
            bypass_mid[1] += perp_lon * lon_off_deg * expand_step
            bypass_out[0] += perp_lat * lat_off_deg * expand_step
            bypass_out[1] += perp_lon * lon_off_deg * expand_step
        
        # 插入绕行点替换原碰撞航段
        path.pop(seg_idx+1)
        path.insert(seg_idx+1, bypass_in)
        path.insert(seg_idx+2, bypass_mid)
        path.insert(seg_idx+3, bypass_out)
    
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
st.markdown("**分组作业6-项目Demo | 地图显示·障碍圈选·航线规划·飞行监控**")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.subheader("🌐 坐标系配置")
    st.selectbox("输入坐标系", ["WGS-84（高德卫星图）", "GCJ-02 (高德/百度)"])
    st.markdown("---")
    st.subheader("📊 系统状态")
    st.success("✅ 系统正常待机")
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
        st.subheader("🗺️ 卫星地图（障碍圈选）")
        m = folium.Map(location=CAMPUS, zoom_start=17, control_scale=True)
        # 高德卫星底图
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
        # 渲染障碍物（红色填充，匹配参考图）
        for obs_data in st.session_state.obstacles:
            obs = Obstacle.from_dict(obs_data)
            line_color = "red" if alt < obs.height else "green"
            folium.Polygon(
                obs.points, color=line_color, weight=2, fill=True,
                fill_color="red", fill_opacity=0.5,
                popup=f"{obs.name}\n高度：{obs.height}m"
            ).add_to(m)
            # 飞行高度不足时显示蓝色安全缓冲区
            if alt < obs.height:
                buf_coords = obs.get_safe_buffer(st.session_state.safe_radius, st.session_state.bypass_distance)
                folium.Polygon(
                    buf_coords, color="blue", weight=1, dash_array="5,5", fill=False,
                    popup=f"安全缓冲区 {total_buf_w}m"
                ).add_to(m)

        # 起终点标记
        folium.Marker(st.session_state.point_a, popup="🚁 起点", icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(st.session_state.point_b, popup="🎯 终点", icon=folium.Icon(color="red", icon="flag")).add_to(m)

        # 渲染规划航线（蓝色虚线，匹配参考图样式）
        if st.session_state.selected_plan:
            plan = st.session_state.selected_plan
            folium.PolyLine(
                plan["points"], color=plan["color"], weight=3, 
                opacity=0.9, dash_array='8, 4'
            ).add_to(m)
            # 绕行拐点标记
            for idx, wp in enumerate(plan["points"][1:-1], 1):
                folium.CircleMarker(
                    wp, radius=4, color="white", fill=True, 
                    fill_color="blue", popup=f"航点{idx}"
                ).add_to(m)

        # 绘图工具、测距、图层控制
        plugins.Draw(draw_options={"polygon": {"allowIntersection": False}}).add_to(m)
        plugins.MeasureControl(primary_length_unit='meters').add_to(m)
        folium.LayerControl().add_to(m)
        map_out = st_folium(m, width="100%", height=550, key="main_map")

        # 捕获绘制的多边形障碍物
        if map_out and map_out.get("last_active_drawing"):
            draw_data = map_out["last_active_drawing"]
            if draw_data["geometry"]["type"] == "Polygon":
                pts = [[coord[1], coord[0]] for coord in draw_data["geometry"]["coordinates"][0]]
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 已绘制障碍物，顶点数：{len(pts)}")

    with col_ctrl:
        # 新建障碍物弹窗
        if st.session_state.show_height_panel and st.session_state.temp_obs:
            st.markdown("### 🆕 新建障碍物")
            obs_name = st.text_input("障碍物名称", value=st.session_state.temp_name)
            st.session_state.temp_name = obs_name if obs_name else "建筑物"
            obs_h = st.number_input("障碍物高度(m)", min_value=1, max_value=200, step=5, value=st.session_state.temp_height)
            st.session_state.temp_height = obs_h
            fly_h = st.session_state.flight_alt
            if fly_h < obs_h:
                st.warning(f"⚠️ 飞行高度{fly_h}m < 建筑高度{obs_h}m，自动绕行")
            else:
                st.success(f"✅ 高度足够，可直接飞越")
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

        # 起终点设置
        st.markdown("### 🚁 起点坐标")
        c_a1, c_a2 = st.columns(2)
        lat_a = c_a1.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
        lon_a = c_a2.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("📍 更新起点", use_container_width=True):
            st.session_state.point_a = [lat_a, lon_a]
            save_waypoints()
            st.rerun()

        st.markdown("### 🎯 终点坐标")
        c_b1, c_b2 = st.columns(2)
        lat_b = c_b1.number_input("纬度", value=st.session_state.point_b[0], format="%.6f", key="latb")
        lon_b = c_b2.number_input("经度", value=st.session_state.point_b[1], format="%.6f", key="lonb")
        if st.button("🏁 更新终点", use_container_width=True):
            st.session_state.point_b = [lat_b, lon_b]
            save_waypoints()
            st.rerun()

        st.markdown("---")
        st.markdown("### ⚙️ 飞行安全参数")
        alt_slider = st.slider("飞行高度(m)", min_value=10, max_value=100, value=st.session_state.flight_alt)
        st.session_state.flight_alt = alt_slider
        safe_slider = st.slider("安全半径(m)", min_value=3, max_value=30, value=st.session_state.safe_radius)
        st.session_state.safe_radius = safe_slider
        bypass_slider = st.slider("绕行距离(m)", min_value=5, max_value=60, value=st.session_state.bypass_distance)
        st.session_state.bypass_distance = bypass_slider
        st.info(f"🛡️ 总安全缓冲距离：{safe_slider + bypass_slider} m")

        # 障碍物高度校验
        if st.session_state.obstacles:
            st.markdown("**📊 障碍高度校验**")
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    st.warning(f"🔄 {obs.name}({obs.height}m) → 需绕行")
                else:
                    st.success(f"✅ {obs.name} → 可飞越")

        st.markdown("---")
        st.markdown("### 🚧 已保存障碍物")
        for idx, obs_data in enumerate(st.session_state.obstacles):
            obs = Obstacle.from_dict(obs_data)
            icon_tag = "🔄" if alt_slider < obs.height else "⬆️"
            with st.expander(f"{icon_tag} {obs.name} 高度{obs.height}m"):
                if st.button("删除", key=f"del_obs_{idx}", use_container_width=True):
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
        if st.button("🎯 一键生成航线", use_container_width=True, type="primary"):
            start_pt = st.session_state.point_a
            end_pt = st.session_state.point_b
            straight_dist = calc_distance(start_pt, end_pt)
            
            # 筛选需绕行的障碍物
            block_obs = []
            block_bufs = []
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    buf_poly = obs.get_safe_buffer(safe_slider, bypass_slider)
                    block_obs.append(obs)
                    block_bufs.append(buf_poly)
            
            plan_list = []
            if len(block_obs) == 0:
                plan_list.append({
                    "name": "📏 直线飞越",
                    "points": [start_pt, end_pt],
                    "dist": straight_dist,
                    "color": "blue",
                    "desc": "无遮挡，直线直达"
                })
            else:
                # 左右两套绕行方案
                dir_config = [("left", "⬅️ 左侧绕行", "#1976d2"), ("right", "➡️ 右侧绕行", "#7b1fa2")]
                for side, name, color in dir_config:
                    path = generate_bypass_path(start_pt, end_pt, block_obs, block_bufs, side, safe_slider, bypass_slider)
                    dist_total, _ = calc_path_total_dist(path)
                    plan_list.append({
                        "name": name,
                        "points": path,
                        "dist": dist_total,
                        "color": color,
                        "desc": f"沿建筑外侧绕行，共{len(path)-2}个航点"
                    })
                # 最优最短航线
                best_plan = min(plan_list, key=lambda x: x["dist"]).copy()
                best_plan["name"] = "⭐ 最优最短航线"
                best_plan["color"] = "#ff8f00"
                best_plan["desc"] = f"路径最短，总长{best_plan['dist']:.1f}m"
                plan_list.append(best_plan)
            
            st.session_state.route_plans = plan_list
            st.session_state.selected_plan = plan_list[-1]
            st.rerun()

        # 方案列表
        if st.session_state.route_plans:
            st.markdown("---")
            st.markdown("### 📋 可选方案")
            for idx, p_item in enumerate(st.session_state.route_plans):
                col_n, col_d = st.columns([2,1])
                with col_n:
                    st.markdown(f"**{p_item['name']}**")
                    st.caption(p_item["desc"])
                with col_d:
                    st.metric("总长", f"{p_item['dist']:.0f}m")
                if st.session_state.selected_plan and st.session_state.selected_plan["name"] == p_item["name"]:
                    st.success("✅ 已选中")
                else:
                    if st.button(f"选用此方案", key=f"sel_plan_{idx}", use_container_width=True):
                        st.session_state.selected_plan = p_item
                        st.rerun()
                st.markdown("---")

            if st.session_state.selected_plan:
                sel_plan = st.session_state.selected_plan
                if st.button("✈️ 确认锁定航线", use_container_width=True, type="primary"):
                    st.session_state.confirmed_plan = sel_plan
                    st.success("✅ 航线已锁定，切换至飞行监控页启动任务")
                    st.balloons()

        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 已锁定执行航线")
            fix_plan = st.session_state.confirmed_plan
            st.success(f"**{fix_plan['name']}** | 总长{fix_plan['dist']:.0f}m")

# ========== Tab2：飞行监控 ==========
with tab2:
    st.subheader("📡 飞行实时画面 - 任务执行监控")
    col_ctrl, col_data = st.columns([1, 3])
    
    with col_ctrl:
        st.markdown("### 🎮 任务控制")
        if st.button("📥 导入已确认航线", use_container_width=True):
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
                st.success(f"✅ 航线载入完成")
                st.rerun()

        wp_list = st.session_state.flight_sim_waypoints
        seg_dist_list = st.session_state.flight_sim_segment_distances
        total_dist_sim = st.session_state.flight_sim_total_distance

        st.markdown("---")
        sim_speed = st.slider("飞行速度(m/s)", min_value=1.0, max_value=20.0, step=0.5, value=st.session_state.flight_sim_speed)
        st.session_state.flight_sim_speed = sim_speed

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("▶️ 开始", use_container_width=True, disabled=(len(wp_list)==0)):
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                else:
                    # 从暂停恢复
                    pause_duration = time.time() - st.session_state.flight_sim_pause_time
                    st.session_state.flight_sim_start_time += pause_duration
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
            if st.button("⏹️ 停止", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_pause_time = 0
                add_fcu_to_gcs_log("FCU→GCS: 任务终止")
                st.rerun()
        with c4:
            if st.button("🔄 重置", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_pause_time = 0
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                st.rerun()

        status_text = "飞行中" if st.session_state.flight_sim_running else "已暂停"
        st.caption(f"当前状态：**{status_text}**")

    with col_data:
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

                # 航点抵达日志
                if curr_wp_idx > st.session_state.flight_sim_last_wp_index:
                    st.session_state.flight_sim_last_wp_index = curr_wp_idx
                    add_fcu_to_gcs_log(f"FCU→GCS: 抵达航点 #{curr_wp_idx+1}")
                    if curr_wp_idx >= len(wp_list)-1:
                        add_fcu_to_gcs_log("FCU→GCS: MISSION_COMPLETE 任务完成")
                        add_business_log("全部航点飞行完毕，任务结束", color="green")

            # 数据面板（匹配作业参考图）
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            d1.metric("当前航点", f"{min(curr_wp_idx+1, len(wp_list))}/{len(wp_list)}")
            d2.metric("飞行速度", f"{sim_speed:.1f} m/s")
            d3.metric("已用时间", f"{time_elapse//60:02d}:{time_elapse%60:02d}")
            d4.metric("剩余距离", f"{remain_d:.0f} m")
            d5.metric("预计到达", f"{time_remain//60:02d}:{time_remain%60:02d}")
            d6.metric("电量模拟", f"{batt:.0f}%")

            st.caption(f"任务进度：{progress*100:.0f}%")
            st.progress(progress)

            st.markdown("---")
            # 实时飞行地图 + 通信链路
            map_col, link_col = st.columns([1.5, 1])
            with map_col:
                st.markdown("**🗺️ 实时飞行地图**")
                m2 = folium.Map(location=CAMPUS, zoom_start=17)
                folium.TileLayer(
                    "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
                    attr="高德卫星", subdomains=["1","2","3","4"]
                ).add_to(m2)
                # 障碍物
                for obs_data in st.session_state.obstacles:
                    obs = Obstacle.from_dict(obs_data)
                    folium.Polygon(obs.points, color="red", fill=True, fill_opacity=0.5).add_to(m2)
                # 航线
                folium.PolyLine(wp_list, color="green", weight=3, dash_array='8,4').add_to(m2)
                # 飞机实时位置
                folium.Marker(
                    [curr_lat, curr_lon], popup="无人机实时位置",
                    icon=folium.Icon(color="green", icon="plane")
                ).add_to(m2)
                st_folium(m2, width="100%", height=300, key="flight_map")

            with link_col:
                st.markdown("**📶 通信链路拓扑与数据流**")
                st.success("✅ GCS 地面站 在线")
                st.info("📡 UDP: 4500")
                st.success("✅ OBC 机载计算机 在线")
                st.info("📡 MAVLink #1")
                st.success("✅ FCU 飞控 在线")
                
                st.markdown("---")
                st.markdown("**💓 心跳检测**")
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

            # 自动刷新
            if st.session_state.flight_sim_running:
                st.rerun()
        else:
            st.info("📭 暂无航线数据，请先导入已确认的航线")

st.markdown("---")
st.caption("无人机智能化应用2451 | 分组作业6-项目Demo")
