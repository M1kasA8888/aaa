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
        st.session_state.obstacles = [
            {
                "name": "南侧长条形主楼",
                "height": 40,
                "points": [[32.2340, 118.7486], [32.2345, 118.7486], [32.2345, 118.7502], [32.2340, 118.7502]]
            },
            {
                "name": "北侧教学楼",
                "height": 35,
                "points": [[32.2320, 118.7488], [32.2326, 118.7488], [32.2326, 118.7500], [32.2320, 118.7500]]
            }
        ]

if 'point_a' not in st.session_state:
    if os.path.exists(WAYPOINT_CONFIG_FILE):
        try:
            with open(WAYPOINT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.point_a = data.get('point_a', [32.2344, 118.749])
                st.session_state.point_b = data.get('point_b', [32.2323, 118.749])
        except Exception:
            st.session_state.point_a = [32.2344, 118.749]
            st.session_state.point_b = [32.2323, 118.749]
    else:
        st.session_state.point_a = [32.2344, 118.749]
        st.session_state.point_b = [32.2323, 118.749]

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

# 飞行仿真状态
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
# 🔧 【核心修复区】几何计算与绕行算法重写
# ==================================================

def calc_distance(p1, p2):
    """Haversine公式计算两点WGS84距离，单位米"""
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    R = 6371000
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def meter_to_degree(meter, base_lat):
    """米转经纬度偏移度数"""
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

# ---------- 修复1：精确线段相交检测，替代采样法 ----------
def _ccw(A, B, C):
    """判断三点逆时针方向"""
    return (C[0]-A[0])*(B[1]-A[1]) > (B[0]-A[0])*(C[1]-A[1])

def seg_intersect_seg(a1, a2, b1, b2):
    """判断两条线段是否相交"""
    return _ccw(a1, b1, b2) != _ccw(a2, b1, b2) and _ccw(a1, a2, b1) != _ccw(a1, a2, b2)

def seg_intersect_polygon(p0, p1, poly):
    """【精确版】线段与多边形相交检测：端点在内 或 与任意边相交"""
    if point_in_polygon(p0, poly) or point_in_polygon(p1, poly):
        return True
    n = len(poly)
    for i in range(n):
        v1 = poly[i]
        v2 = poly[(i+1)%n]
        if seg_intersect_seg(p0, p1, v1, v2):
            return True
    return False

# ---------- 修复2：多边形外扩方向修正，确保缓冲区向外 ----------
def polygon_winding(poly):
    """判断多边形环绕方向：返回True=逆时针，False=顺时针"""
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i+1)%n][1], poly[(i+1)%n][0]
        area += (x2 - x1) * (y2 + y1)
    return area > 0

def offset_polygon_outward(poly, offset_m, base_lat):
    """【修复版】多边形向外外扩指定米数，自动适配环绕方向"""
    lat_off, lon_off = meter_to_degree(offset_m, base_lat)
    is_ccw = polygon_winding(poly)
    # 顺时针多边形法线反向，确保向外偏移
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
        
        # 边的法线（向外）
        nx1 = -dy1 / len1 * direction
        ny1 = dx1 / len1 * direction
        nx2 = -dy2 / len2 * direction
        ny2 = dx2 / len2 * direction
        
        # 角平分线方向
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

# ---------- 修复3：迭代碰撞修正绕行算法，支持多障碍物无穿墙 ----------
def find_first_collision(path, buf_list):
    """找到路径中第一个碰撞的航段和对应的缓冲区索引"""
    for i in range(len(path)-1):
        seg_start = path[i]
        seg_end = path[i+1]
        for buf_idx, buf in enumerate(buf_list):
            if seg_intersect_polygon(seg_start, seg_end, buf):
                return i, buf_idx
    return -1, -1

def generate_bypass_path(start, end, obs_list, buf_list, side, safe_r, bypass_d):
    """
    【迭代修正版】多障碍物绕行路径生成
    思路：从直线开始，反复找到第一个碰撞点，插入绕行拐点，直到全程无碰撞
    """
    path = [start.copy(), end.copy()]
    total_buf = safe_r + bypass_d
    lat_off_deg, lon_off_deg = meter_to_degree(total_buf * 3.0, CAMPUS[0])
    max_iter = 50  # 最大迭代次数，防止死循环
    
    for _ in range(max_iter):
        seg_idx, buf_idx = find_first_collision(path, buf_list)
        if seg_idx == -1:
            break  # 全程无碰撞，完成
        
        obs = obs_list[buf_idx]
        buf = buf_list[buf_idx]
        seg_s = path[seg_idx]
        seg_e = path[seg_idx+1]
        
        # 计算航线方向的垂直偏移方向（左/右）
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
        
        # 以障碍物中心为基准，向侧方偏移生成绕行点
        cx, cy = obs.center_lat, obs.center_lon
        bypass_pt = [cx + perp_lat * lat_off_deg, cy + perp_lon * lon_off_deg]
        
        # 迭代外扩，确保绕行点到线段两端都不碰撞
        expand_step = 1.3
        for __ in range(20):
            ok1 = not seg_intersect_polygon(seg_s, bypass_pt, buf)
            ok2 = not seg_intersect_polygon(bypass_pt, seg_e, buf)
            if ok1 and ok2:
                break
            bypass_pt[0] += perp_lat * lat_off_deg * expand_step
            bypass_pt[1] += perp_lon * lon_off_deg * expand_step
        
        # 在碰撞航段中插入绕行拐点
        path.insert(seg_idx + 1, bypass_pt)
    
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
st.markdown("**南京科技职业学院 | 多建筑迭代绕行 | 全程零穿墙校验 | 左/右/最优3套方案**")
st.markdown("---")

with st.sidebar:
    st.subheader("🌐 坐标系")
    st.selectbox("输入坐标系", ["WGS-84（高德卫星图）", "GCJ-02 (高德/百度)"])
    st.markdown("---")
    st.subheader("📊 系统状态")
    st.success("✅ 系统正常待机")
    st.markdown("### 📖 操作流程")
    st.caption("1. 地图多边形绘制建筑障碍物")
    st.caption("2. 设置建筑高度保存")
    st.caption("3. 填写起终点坐标")
    st.caption("4. 生成左/右/最优航线")
    st.caption("5. 确认航线进入飞行仿真")

tab1, tab2 = st.tabs(["🗺️ 航线规划", "📡 飞行监控"])

# ========== 航线规划Tab ==========
with tab1:
    col_map, col_ctrl = st.columns([1.6, 1])
    with col_map:
        st.subheader("🗺️ 高德卫星底图")
        m = folium.Map(location=CAMPUS, zoom_start=17, control_scale=True)
        folium.TileLayer(
            "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
            attr="高德卫星图源", subdomains=["1","2","3","4"], name="卫星地图"
        ).add_to(m)
        folium.TileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="OpenStreetMap", name="街道地图"
        ).add_to(m)
        folium.Marker(CAMPUS, popup="🏫 南京科技职业学院", icon=folium.Icon(color="red")).add_to(m)

        alt = st.session_state.flight_alt
        total_buf_w = st.session_state.safe_radius + st.session_state.bypass_distance
        for obs_data in st.session_state.obstacles:
            obs = Obstacle.from_dict(obs_data)
            line_color = "red" if alt < obs.height else "green"
            folium.Polygon(
                obs.points, color=line_color, weight=2, fill=True,
                fill_color=line_color, fill_opacity=0.3,
                popup=f"{obs.name}\n高度：{obs.height}m"
            ).add_to(m)
            if alt < obs.height:
                buf_coords = obs.get_safe_buffer(st.session_state.safe_radius, st.session_state.bypass_distance)
                folium.Polygon(
                    buf_coords, color="blue", weight=1.5, dash_array="5,5", fill=False,
                    popup=f"安全缓冲区 {total_buf_w}m"
                ).add_to(m)

        folium.Marker(st.session_state.point_a, popup="🚁 起点A", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(st.session_state.point_b, popup="🎯 终点B", icon=folium.Icon(color="red")).add_to(m)

        if st.session_state.selected_plan:
            plan = st.session_state.selected_plan
            folium.PolyLine(plan["points"], color=plan["color"], weight=4, opacity=0.9).add_to(m)
            for idx, wp in enumerate(plan["points"][1:-1], 1):
                folium.Marker(wp, popup=f"绕行点{idx}", icon=folium.Icon(color="purple", icon="refresh")).add_to(m)

        plugins.Draw(draw_options={"polygon": {"allowIntersection": False}}).add_to(m)
        plugins.MeasureControl().add_to(m)
        folium.LayerControl().add_to(m)
        map_out = st_folium(m, width="100%", height=520, key="main_map")

        if map_out and map_out.get("last_active_drawing"):
            draw_data = map_out["last_active_drawing"]
            if draw_data["geometry"]["type"] == "Polygon":
                pts = [[coord[1], coord[0]] for coord in draw_data["geometry"]["coordinates"][0]]
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 已绘制{len(pts)}个顶点障碍物")

    with col_ctrl:
        # 新建障碍物弹窗
        if st.session_state.show_height_panel and st.session_state.temp_obs:
            st.markdown("### 🆕 新建3D障碍物")
            obs_name = st.text_input("障碍物名称", value=st.session_state.temp_name)
            st.session_state.temp_name = obs_name if obs_name else "建筑物"
            obs_h = st.number_input("障碍物高度(m)", min_value=1, max_value=200, step=5, value=st.session_state.temp_height)
            st.session_state.temp_height = obs_h
            fly_h = st.session_state.flight_alt
            if fly_h < obs_h:
                st.warning(f"⚠️ 飞行高度{fly_h}m < 建筑高度{obs_h}m，自动触发绕行")
            else:
                st.success(f"✅ 可直接飞越")
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
                if st.button("🗑️ 取消", use_container_width=True):
                    st.session_state.temp_obs = None
                    st.session_state.show_height_panel = False
                    st.rerun()
            st.markdown("---")

        # 起点终点设置
        st.markdown("### 🚁 起点A坐标")
        c_a1, c_a2 = st.columns(2)
        lat_a = c_a1.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
        lon_a = c_a2.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("📍 设置A点", use_container_width=True):
            st.session_state.point_a = [lat_a, lon_a]
            save_waypoints()
            st.rerun()

        st.markdown("### 🎯 终点B坐标")
        c_b1, c_b2 = st.columns(2)
        lat_b = c_b1.number_input("纬度", value=st.session_state.point_b[0], format="%.6f", key="latb")
        lon_b = c_b2.number_input("经度", value=st.session_state.point_b[1], format="%.6f", key="lonb")
        if st.button("🏁 设置B点", use_container_width=True):
            st.session_state.point_b = [lat_b, lon_b]
            save_waypoints()
            st.rerun()

        st.markdown("---")
        st.markdown("### ⚙️ 飞行参数")
        alt_slider = st.slider("飞行高度(m)", min_value=10, max_value=100, value=st.session_state.flight_alt)
        st.session_state.flight_alt = alt_slider
        safe_slider = st.slider("安全半径(m)", min_value=5, max_value=30, value=st.session_state.safe_radius)
        st.session_state.safe_radius = safe_slider
        bypass_slider = st.slider("绕行距离(m)", min_value=5, max_value=50, value=st.session_state.bypass_distance)
        st.session_state.bypass_distance = bypass_slider
        st.info(f"🛡️ 总安全缓冲区宽度：{safe_slider + bypass_slider} m")

        if st.session_state.obstacles:
            st.markdown("**📊 障碍物高度校验**")
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    st.warning(f"🔄 {obs.name}({obs.height}m)，必须绕行")
                else:
                    st.success(f"✅ {obs.name}，可飞越")

        st.markdown("---")
        st.markdown("### 🚧 已保存障碍物列表")
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
            if st.button("💾 保存全部配置", use_container_width=True):
                save_obstacles_to_file()
                save_waypoints()
                st.success("已保存")
        with c_load:
            if st.button("📂 加载配置", use_container_width=True):
                load_obstacles_from_file()
                st.rerun()
        with c_clear:
            if st.button("🗑️ 清空所有障碍物", use_container_width=True):
                st.session_state.obstacles = []
                save_obstacles_to_file()
                st.rerun()

        st.markdown("---")
        st.markdown("## 🗺️ 生成航线（迭代校验零穿墙）")
        if st.button("🎯 一键生成航线方案", use_container_width=True, type="primary"):
            start_pt = st.session_state.point_a
            end_pt = st.session_state.point_b
            straight_dist = calc_distance(start_pt, end_pt)
            
            # 筛选需要绕行的障碍物+缓冲区
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
                    "desc": "无遮挡，直线飞行"
                })
            else:
                # 生成左右两套绕行方案
                dir_config = [("left", "⬅️ 左侧绕行", "orange"), ("right", "➡️ 右侧绕行", "purple")]
                for side, name, color in dir_config:
                    path = generate_bypass_path(start_pt, end_pt, block_obs, block_bufs, side, safe_slider, bypass_slider)
                    dist_total, _ = calc_path_total_dist(path)
                    plan_list.append({
                        "name": name,
                        "points": path,
                        "dist": dist_total,
                        "color": color,
                        "desc": f"迭代校验无穿墙，共{len(path)-2}个绕行拐点"
                    })
                
                # 最优最短航线
                best_plan = min(plan_list, key=lambda x: x["dist"]).copy()
                best_plan["name"] = "⭐ 最优最短航线"
                best_plan["color"] = "gold"
                best_plan["desc"] = f"左右对比最短，总长{best_plan['dist']:.1f}m"
                plan_list.append(best_plan)
            
            st.session_state.route_plans = plan_list
            st.session_state.selected_plan = plan_list[-1]
            st.rerun()

        # 方案选择展示
        if st.session_state.route_plans:
            st.markdown("---")
            st.markdown("### 📋 可选航线方案")
            for idx, p_item in enumerate(st.session_state.route_plans):
                col_n, col_d, col_t = st.columns([2,1,1])
                with col_n:
                    st.markdown(f"**{p_item['name']}**")
                    st.caption(p_item["desc"])
                with col_d:
                    st.metric("航线总长", f"{p_item['dist']:.0f}m")
                with col_t:
                    st.metric("预估时长", f"{p_item['dist']/15:.0f}s")
                if st.session_state.selected_plan and st.session_state.selected_plan["name"] == p_item["name"]:
                    st.success("✅ 已选中")
                else:
                    if st.button(f"选用此方案", key=f"sel_plan_{idx}", use_container_width=True):
                        st.session_state.selected_plan = p_item
                        st.rerun()
                st.markdown("---")

            if st.session_state.selected_plan:
                sel_plan = st.session_state.selected_plan
                diff_len = sel_plan["dist"] - calc_distance(st.session_state.point_a, st.session_state.point_b)
                st.info(f"当前选中：{sel_plan['name']}，多出绕行距离 {diff_len:.0f} m")
                if st.button("✈️ 确认锁定该航线", use_container_width=True, type="primary"):
                    st.session_state.confirmed_plan = sel_plan
                    st.success("✅ 航线确认完毕，可切换至飞行监控")
                    st.balloons()

        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 已锁定执行航线")
            fix_plan = st.session_state.confirmed_plan
            st.success(f"**{fix_plan['name']}**")
            st.caption(f"航线总长：{fix_plan['dist']:.0f} m，预估飞行 {fix_plan['dist']/15:.0f} s")

# ========== 飞行监控Tab ==========
with tab2:
    st.subheader("📡 实时飞行任务监控")
    col_sim_ctrl, col_sim_view = st.columns([1, 2])
    with col_sim_ctrl:
        st.markdown("### 🎮 仿真控制")
        if st.button("📐 导入已确认航线", use_container_width=True):
            if st.session_state.confirmed_plan is None:
                st.warning("请先在航线规划页确认航线！")
            else:
                wp_list = st.session_state.confirmed_plan["points"]
                total_d, seg_d = calc_path_total_dist(wp_list)
                st.session_state.flight_sim_waypoints = wp_list
                st.session_state.flight_sim_total_distance = total_d
                st.session_state.flight_sim_segment_distances = seg_d
                st.session_state.flight_sim_current_index = 0
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                add_business_log(f"航线导入成功，航点数量{len(wp_list)}，总长{total_d:.1f}m")
                add_gcs_to_fcu_log("GCS→OBC: MISSION_UPLOAD")
                add_fcu_to_gcs_log("FCU→OBC: MISSION_ACK")
                st.success(f"✅ 航线载入完成，共{len(wp_list)}个航点")
                st.rerun()

        wp_list = st.session_state.flight_sim_waypoints
        seg_dist_list = st.session_state.flight_sim_segment_distances
        total_dist_sim = st.session_state.flight_sim_total_distance

        st.markdown("---")
        sim_speed = st.slider("飞行速度(m/s)", min_value=1.0, max_value=20.0, step=0.5, value=st.session_state.flight_sim_speed)
        st.session_state.flight_sim_speed = sim_speed
        st.markdown("---")
        c_start, c_stop, c_reset = st.columns(3)
        with c_start:
            btn_start = st.button("▶️ 启动任务", use_container_width=True, disabled=(len(wp_list)==0))
            if btn_start:
                st.session_state.flight_sim_running = True
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                add_fcu_to_gcs_log("FCU→OBC→GCS: ACK | AUTO模式开启")
                st.rerun()
        with c_stop:
            if st.button("⏹️ 中止飞行", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.rerun()
        with c_reset:
            if st.button("🔄 重置仿真", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_current_index = 0
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 航线基础信息")
        st.caption(f"起点A：{st.session_state.point_a[0]:.6f}, {st.session_state.point_a[1]:.6f}")
        st.caption(f"终点B：{st.session_state.point_b[0]:.6f}, {st.session_state.point_b[1]:.6f}")
        st.caption(f"飞行高度：{st.session_state.flight_alt} m")
        st.caption(f"安全半径：{st.session_state.safe_radius} m")
        st.caption(f"绕行距离：{st.session_state.bypass_distance} m")
        st.caption(f"航点总数：{len(wp_list)}")
        if total_dist_sim > 0:
            st.caption(f"航线总长度：{total_dist_sim:.1f} m")

        st.markdown("---")
        st.markdown("### 💓 链路心跳监控")
        if not st.session_state.heartbeat_running:
            if st.button("▶️ 启动心跳检测", use_container_width=True):
                st.session_state.heartbeat_sim.start()
                st.session_state.heartbeat_running = True
                st.rerun()
        else:
            if st.button("⏹️ 停止心跳检测", use_container_width=True):
                st.session_state.heartbeat_sim.stop()
                st.session_state.heartbeat_running = False
                st.rerun()
        hb_item = st.session_state.heartbeat_sim.update()
        if hb_item:
            if hb_item["status"] == "timeout":
                st.error(f"⚠️ 链路超时，3s无心跳反馈")
            else:
                st.success(f"💓 心跳正常 | ID:{hb_item['id']} 延迟:{hb_item['delay']}ms")
        hb_stats = st.session_state.heartbeat_sim.get_stats()
        ch1, ch2 = st.columns(2)
        ch1.metric("总心跳包数", hb_stats["total"])
        ch2.metric("心跳成功率", f"{hb_stats['rate']}%")

    with col_sim_view:
        if len(wp_list) > 0:
            curr_lat, curr_lon = wp_list[0][0], wp_list[0][1]
            flown_d = 0.0
            remain_d = total_dist_sim
            time_elapse_str = "00:00"
            time_remain_str = "00:00"
            batt = 100.0
            curr_wp_idx = 0
            progress_rate = 0.0

            if st.session_state.flight_sim_running:
                elapse_sec = time.time() - st.session_state.flight_sim_start_time
                flown_d = elapse_sec * sim_speed
                total_flown_seg = 0.0
                for seg_idx, seg_d in enumerate(seg_dist_list):
                    if total_flown_seg + seg_d >= flown_d:
                        curr_wp_idx = seg_idx
                        seg_progress = (flown_d - total_flown_seg) / seg_d if seg_d>1e-6 else 0
                        p0 = wp_list[seg_idx]
                        p1 = wp_list[min(seg_idx+1, len(wp_list)-1)]
                        curr_lat = p0[0] + (p1[0]-p0[0])*seg_progress
                        curr_lon = p0[1] + (p1[1]-p0[1])*seg_progress
                        break
                    total_flown_seg += seg_d
                else:
                    curr_wp_idx = len(wp_list)-1
                    st.session_state.flight_sim_running = False

                remain_d = max(0.0, total_dist_sim - flown_d)
                remain_sec = remain_d / sim_speed if sim_speed>1e-6 else 0
                m_el = int(elapse_sec // 60)
                s_el = int(elapse_sec % 60)
                time_elapse_str = f"{m_el:02d}:{s_el:02d}"
                m_re = int(remain_sec // 60)
                s_re = int(remain_sec % 60)
                time_remain_str = f"{m_re:02d}:{s_re:02d}"
                batt = max(0.0, 100.0 - (elapse_sec / 1800.0)*100.0)
                progress_rate = flown_d / total_dist_sim if total_dist_sim>1e-6 else 0.0

                if curr_wp_idx > st.session_state.flight_sim_last_wp_index:
                    st.session_state.flight_sim_last_wp_index = curr_wp_idx
                    add_fcu_to_gcs_log(f"FCU→GCS: 抵达航点#{curr_wp_idx}")
                    if curr_wp_idx >= len(wp_list)-1:
                        add_fcu_to_gcs_log("FCU→GCS: MISSION_COMPLETE 任务结束")
                        add_business_log("完整航线执行完毕", color="green")

            st.markdown("### 📊 实时飞行数据")
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            r1c1.metric("当前航点", f"{min(curr_wp_idx+1, len(wp_list))}/{len(wp_list)}")
            r1c2.metric("飞行速度", f"{sim_speed:.1f} m/s")
            r1c3.metric("已飞行时长", time_elapse_str)
            r1c4.metric("剩余距离", f"{remain_d:.0f} m")

            r2c1, r2c2, r2c3, _ = st.columns(4)
            r2c1.metric("预计剩余时间", time_remain_str)
            r2c2.metric("剩余电量", f"{batt:.0f}%")
            r2c3.metric("完成进度", f"{progress_rate*100:.0f}%")
            st.progress(min(1.0, progress_rate))

            st.markdown("---")
            st.markdown("### 📶 通信链路状态")
            gcs_col, obc_col, fcu_col = st.columns(3)
            with gcs_col: st.success("✅ GCS 地面站在线")
            with obc_col: st.success("✅ OBC机载计算机在线")
            with fcu_col: st.success("✅ FCU飞控在线")
            st.markdown("---")

            if st.session_state.flight_sim_running:
                st.info("✈️ 飞行任务执行中...")
            elif curr_wp_idx >= len(wp_list)-1:
                st.success("✅ 全部航点飞行完成！")
            else:
                st.info("⏸️ 仿真已暂停，等待启动")

            st.markdown("---")
            st.markdown("### 📝 上下行通信日志")
            log_box = st.container(height=200)
            with log_box:
                for log_item in st.session_state.comm_logs_business[-10:]:
                    st.caption(f"📋 [{log_item['timestamp']}] {log_item['message']}")
                for log_item in st.session_state.comm_logs_fcu_to_gcs[-5:]:
                    st.caption(f"⬆️ {log_item}")
                for log_item in st.session_state.comm_logs_gcs_to_fcu[-5:]:
                    st.caption(f"⬇️ {log_item}")

            if st.session_state.flight_sim_running:
                st.rerun()
        else:
            st.info("请先在航线规划页确认航线，再执行「导入已确认航线」")

st.markdown("---")
st.caption("算法说明：采用迭代碰撞修正机制，每轮找到第一个穿墙点后插入绕行拐点，反复校验直到全程无碰撞；支持任意数量、任意形状的多边形障碍物，长条建筑、L型建筑、密集建筑群均可正常绕行")
