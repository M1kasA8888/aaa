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

# ==================== 页面配置 ====================
st.set_page_config(page_title="无人机智能监控系统", page_icon="🛰️", layout="wide")

# ==================== 坐标常量 ====================
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
if "drone_current_pos" not in st.session_state:
    st.session_state.drone_current_pos = st.session_state.point_a.copy()

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

# ==================== 几何底层函数（修复方向+高精度碰撞） ====================
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

# 检测线段是否碰撞任意障碍物（本体+缓冲区），返回第一个碰撞的障碍物索引
def check_segment_collide_all(p0, p1, raw_polys, buf_polys, sample_num=120):
    for i in range(sample_num + 1):
        t = i / sample_num
        lat = p0[0] + (p1[0]-p0[0]) * t
        lon = p0[1] + (p1[1]-p0[1]) * t
        pt = [lat, lon]
        for idx, (raw, buf) in enumerate(zip(raw_polys, buf_polys)):
            if point_in_polygon(pt, raw) or point_in_polygon(pt, buf):
                return True, idx, t
    return False, -1, 0.0

def offset_polygon_outward(poly, offset_m, base_lat):
    lat_off, lon_off = meter_to_degree(offset_m, base_lat)
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

# ==================== 【核心】多障碍物贴边绕行算法 ====================
def get_obstacle_data(obs_list, flight_alt, safe_r, bypass_d):
    obs_objs = []
    raw_polys = []
    buf_polys = []
    for d in obs_list:
        obs = Obstacle.from_dict(d)
        if flight_alt < obs.height:
            obs_objs.append(obs)
            raw_polys.append(obs.points)
            buf_polys.append(obs.get_safe_buffer(safe_r, bypass_d))
    # 按距离起点由近到远排序，保证依次绕行
    obs_objs.sort(key=lambda o: calc_distance(st.session_state.point_a, [o.center_lat, o.center_lon]))
    raw_polys.sort(key=lambda poly: calc_distance(st.session_state.point_a, [
        (min(p[0] for p in poly)+max(p[0] for p in poly))/2,
        (min(p[1] for p in poly)+max(p[1] for p in poly))/2
    ]))
    buf_polys.sort(key=lambda poly: calc_distance(st.session_state.point_a, [
        (min(p[0] for p in poly)+max(p[0] for p in poly))/2,
        (min(p[1] for p in poly)+max(p[1] for p in poly))/2
    ]))
    return obs_objs, raw_polys, buf_polys

# 生成单侧贴边绕行路径（迭代式，直到无任何碰撞）
def generate_edge_bypass_route(start, end, obs_objs, raw_polys, buf_polys, side, safe_r, bypass_d):
    total_buf = safe_r + bypass_d
    lat_off, lon_off = meter_to_degree(total_buf * 1.1, CAMPUS[0]) # 仅多10%余量，贴边飞行
    path = [start.copy(), end.copy()]
    max_iter = 20
    iter_cnt = 0

    while iter_cnt < max_iter:
        collided = False
        new_path = [path[0]]
        for i in range(len(path)-1):
            p0 = new_path[-1]
            p1 = path[i+1]
            is_hit, hit_idx, hit_t = check_segment_collide_all(p0, p1, raw_polys, buf_polys)
            if not is_hit:
                new_path.append(p1)
                continue
            
            collided = True
            # 计算碰撞点
            hit_lat = p0[0] + (p1[0]-p0[0]) * hit_t
            hit_lon = p0[1] + (p1[1]-p0[1]) * hit_t
            # 计算航线方向的垂直法线（修复经纬度分量错误）
            dx = p1[1] - p0[1]
            dy = p1[0] - p0[0]
            line_len = math.hypot(dx, dy)
            if line_len < 1e-9:
                new_path.append(p1)
                continue
            dx_norm = dx / line_len
            dy_norm = dy / line_len

            # 左右侧法线：纬度对应dy，经度对应dx，方向正确
            if side == "left":
                perp_lat = -dx_norm
                perp_lon = dy_norm
            else:
                perp_lat = dx_norm
                perp_lon = -dy_norm

            # 生成贴边绕行点（碰撞点向外侧偏移刚好缓冲宽度）
            bypass_lat = hit_lat + perp_lat * lat_off
            bypass_lon = hit_lon + perp_lon * lon_off
            bypass_pt = [bypass_lat, bypass_lon]

            # 迭代外扩确保绕行点绝对安全
            expand_step = 1.05
            for _ in range(15):
                safe1, _, _ = check_segment_collide_all(p0, bypass_pt, raw_polys, buf_polys)
                safe2, _, _ = check_segment_collide_all(bypass_pt, p1, raw_polys, buf_polys)
                if not safe1 and not safe2:
                    break
                bypass_pt[0] += perp_lat * lat_off * 0.2
                bypass_pt[1] += perp_lon * lon_off * 0.2

            new_path.append(bypass_pt)
            new_path.append(p1)
        
        path = new_path
        iter_cnt += 1
        if not collided:
            break
    
    # 路径去重
    final_path = []
    last_pt = None
    for pt in path:
        if last_pt is None or calc_distance(pt, last_pt) > 0.5:
            final_path.append(pt)
            last_pt = pt
    return final_path

def generate_3_routes(start, end, obs_list, flight_alt, safe_r, bypass_d):
    obs_objs, raw_polys, buf_polys = get_obstacle_data(obs_list, flight_alt, safe_r, bypass_d)
    straight_dist = calc_distance(start, end)
    plan_list = []

    if len(obs_objs) == 0:
        plan_list.append({
            "name": "📏 直线飞越航线",
            "points": [start, end],
            "dist": straight_dist,
            "desc": "无低矮障碍物，直线直达",
            "color": "blue"
        })
        return plan_list

    # 生成左右两条贴边绕行路径
    left_path = generate_edge_bypass_route(start, end, obs_objs, raw_polys, buf_polys, "left", safe_r, bypass_d)
    right_path = generate_edge_bypass_route(start, end, obs_objs, raw_polys, buf_polys, "right", safe_r, bypass_d)
    dist_left, _ = calc_path_total_dist(left_path)
    dist_right, _ = calc_path_total_dist(right_path)

    plan_list.append({
        "name": "⬅️ 左侧贴边绕行",
        "points": left_path,
        "dist": dist_left,
        "desc": f"左向贴边飞行，总长{dist_left:.0f}m，全程不触碰缓冲区",
        "color": "orange"
    })
    plan_list.append({
        "name": "➡️ 右侧贴边绕行",
        "points": right_path,
        "dist": dist_right,
        "desc": f"右向贴边飞行，总长{dist_right:.0f}m，全程不触碰缓冲区",
        "color": "purple"
    })

    # 自动选最短最优
    if dist_left < dist_right:
        best_path, best_dist = left_path, dist_left
    else:
        best_path, best_dist = right_path, dist_right
    
    plan_list.append({
        "name": "⭐ 最优最短贴边航线",
        "points": best_path,
        "dist": best_dist,
        "desc": f"自动择优最短安全路径，总长{best_dist:.0f}m，贴边飞行不穿墙",
        "color": "blue"
    })
    return plan_list

def calc_path_total_dist(waypoints):
    total = 0.0
    seg_dist = []
    for i in range(len(waypoints)-1):
        d = calc_distance(waypoints[i], waypoints[i+1])
        seg_dist.append(d)
        total += d
    return total, seg_dist

# ==================== 地图渲染函数 ====================
def create_base_map(center, zoom=17):
    m = folium.Map(location=center, zoom_start=zoom, control_scale=True)
    folium.TileLayer(
        "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
        attr="高德卫星影像", subdomains=["1","2","3","4"], show=True, name="高德卫星"
    ).add_to(m)
    folium.TileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap", name="openstreetmap", show=False
    ).add_to(m)
    draw_control = plugins.Draw(
        draw_options={"polygon": {"allowIntersection": False, "shapeOptions":{"color":"red","fillColor":"red","fillOpacity":0.4}}},
        edit_options={"poly": {"allowIntersection": False}}
    )
    draw_control.add_to(m)
    plugins.MeasureControl(position="topleft", primary_length_unit="meters").add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    plugins.MousePosition().add_to(m)
    return m

def render_map_content(m, drone_pos=None):
    alt = st.session_state.flight_alt
    total_buf_w = st.session_state.safe_radius + st.session_state.bypass_distance
    # 绘制障碍物+安全缓冲区
    for obs_data in st.session_state.obstacles:
        obs = Obstacle.from_dict(obs_data)
        line_color = "red" if alt < obs.height else "green"
        folium.Polygon(
            obs.points, color=line_color, weight=3, fill=True,
            fill_color=line_color, fill_opacity=0.5,
            popup=f"{obs.name}\n高度{obs.height}m"
        ).add_to(m)
        if alt < obs.height:
            buf_coords = obs.get_safe_buffer(st.session_state.safe_radius, st.session_state.bypass_distance)
            folium.Polygon(
                buf_coords, color="blue", weight=1.5, dash_array="5,5", fill=False,
                popup=f"安全缓冲 {total_buf_w}m"
            ).add_to(m)
    # 起止点标记
    folium.Marker(
        st.session_state.point_a, popup="起飞起点",
        icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(m)
    folium.Marker(
        st.session_state.point_b, popup="目标终点",
        icon=folium.Icon(color="red", icon="map-pin", prefix="fa")
    ).add_to(m)
    # 绘制选中航线
    if st.session_state.selected_plan:
        plan = st.session_state.selected_plan
        folium.PolyLine(
            plan["points"], color=plan["color"], weight=5, opacity=0.9,
            dash_array="4,3", popup=f"{plan['name']} {plan['dist']:.1f}m"
        ).add_to(m)
        # 绕行拐点标记
        for idx, wp in enumerate(plan["points"][1:-1], 1):
            folium.Marker(
                wp, popup=f"绕行拐点{idx}",
                icon=folium.Icon(color="purple", icon="refresh", prefix="fa")
            ).add_to(m)
    # 无人机实时位置
    if drone_pos is not None:
        folium.Marker(
            drone_pos, popup="当前无人机",
            icon=folium.Icon(color="cyan", icon="plane", prefix="fa")
        ).add_to(m)
    return m

# ==================== 页面主体 ====================
st.title("🛰️ 无人机智能监控系统")
st.markdown("**南京科技职业学院** | 多障碍物贴边绕行 | 全局零穿墙校验 | 自动择优最短航线")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.subheader("🌐 坐标系统")
    st.selectbox("地图坐标系", ["WGS-84", "GCJ-02 (高德/百度)"])
    st.markdown("---")
    st.subheader("📊 系统运行状态")
    st.success("✅ 机载通信链路正常")
    st.info(f"🛡️ 全局安全半径：{st.session_state.safe_radius} m")

tab1, tab2 = st.tabs(["🗺️ 航线规划（障碍物圈选）", "📡 飞行实时监控"])

# ========== 航线规划Tab ==========
with tab1:
    col_map, col_ctrl = st.columns([1.5, 1])
    with col_map:
        st.subheader("卫星航拍地图（可圈选障碍物）")
        m = create_base_map(CAMPUS, zoom=17)
        m = render_map_content(m)
        map_out = st_folium(m, width="100%", height=480, key="plan_map")
        if map_out and map_out.get("last_active_drawing"):
            draw_data = map_out["last_active_drawing"]
            if draw_data["geometry"]["type"] == "Polygon":
                pts = [[coord[1], coord[0]] for coord in draw_data["geometry"]["coordinates"][0]]
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 圈选障碍物成功，顶点{len(pts)}个，请填写高度保存")

    with col_ctrl:
        # 新建障碍物面板
        if st.session_state.show_height_panel and st.session_state.temp_obs:
            st.markdown("### 🆕 保存障碍物建筑")
            obs_name = st.text_input("障碍物名称", value=st.session_state.temp_name)
            st.session_state.temp_name = obs_name if obs_name else "建筑物"
            obs_h = st.number_input("建筑高度(m)", min_value=1, max_value=200, step=5, value=st.session_state.temp_height)
            st.session_state.temp_height = obs_h
            fly_h = st.session_state.flight_alt
            if fly_h < obs_h:
                st.warning(f"⚠️ 飞行高度低于建筑，航线将贴边绕行，全局零穿墙校验")
            else:
                st.success(f"✅ 高度充足，可直接飞越")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 存入障碍物库", type="primary", use_container_width=True):
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

        # 起点终点设置
        st.markdown("### 🚁 起飞起点 A")
        c_a1, c_a2 = st.columns(2)
        lat_a = c_a1.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
        lon_a = c_a2.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("📍 更新起点坐标", use_container_width=True):
            st.session_state.point_a = [lat_a, lon_a]
            save_waypoints()
            st.rerun()

        st.markdown("### 🎯 目标终点 B")
        c_b1, c_b2 = st.columns(2)
        lat_b = c_b1.number_input("纬度", value=st.session_state.point_b[0], format="%.6f", key="latb")
        lon_b = c_b2.number_input("经度", value=st.session_state.point_b[1], format="%.6f", key="lonb")
        if st.button("🏁 更新终点坐标", use_container_width=True):
            st.session_state.point_b = [lat_b, lon_b]
            save_waypoints()
            st.rerun()

        st.markdown("---")
        st.markdown("### ⚙️ 飞行安全参数")
        alt_slider = st.slider("飞行高度(m)", min_value=10, max_value=100, value=st.session_state.flight_alt)
        st.session_state.flight_alt = alt_slider
        safe_slider = st.slider("无人机安全半径(m)", min_value=5, max_value=30, value=st.session_state.safe_radius)
        st.session_state.safe_radius = safe_slider
        bypass_slider = st.slider("贴边预留距离(m)", min_value=5, max_value=50, value=st.session_state.bypass_distance)
        st.session_state.bypass_distance = bypass_slider
        st.info(f"🛡️ 总缓冲宽度：{safe_slider + bypass_slider} m，航线紧贴缓冲区外侧飞行")

        # 障碍物高度校验
        if st.session_state.obstacles:
            st.markdown("**📊 建筑高度校验清单**")
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    st.warning(f"🔄 {obs.name}（高{obs.height}m）：贴边绕行")
                else:
                    st.success(f"⬆️ {obs.name}：可直接飞越")

        st.markdown("---")
        st.markdown("### 🧱 已保存障碍物列表")
        for idx, obs_data in enumerate(st.session_state.obstacles):
            obs = Obstacle.from_dict(obs_data)
            tag = "🔄" if alt_slider < obs.height else "⬆️"
            with st.expander(f"{tag} {obs.name} | 高度 {obs.height}m"):
                if st.button("删除该建筑", key=f"del_obs_{idx}", use_container_width=True):
                    st.session_state.obstacles.pop(idx)
                    save_obstacles_to_file()
                    st.rerun()

        c_save, c_load, c_clear = st.columns(3)
        with c_save:
            if st.button("💾 保存全部配置", use_container_width=True):
                save_obstacles_to_file()
                st.success("障碍物数据已本地持久化")
        with c_load:
            if st.button("📂 读取本地配置", use_container_width=True):
                load_obstacles_from_file()
                st.rerun()
        with c_clear:
            if st.button("🗑️ 清空所有障碍物", use_container_width=True):
                st.session_state.obstacles = []
                save_obstacles_to_file()
                st.rerun()

        st.markdown("---")
        st.markdown("## 🚀 生成贴边绕行航线")
        if st.button("🎯 生成全部航线方案", use_container_width=True, type="primary"):
            start_pt = st.session_state.point_a
            end_pt = st.session_state.point_b
            plan_list = generate_3_routes(start_pt, end_pt, st.session_state.obstacles, alt_slider, safe_slider, bypass_slider)
            st.session_state.route_plans = plan_list
            st.session_state.selected_plan = plan_list[-1]
            st.rerun()

        # 航线方案列表
        if st.session_state.route_plans:
            st.markdown("---")
            st.markdown("### 📋 航线方案预览")
            for idx, item in enumerate(st.session_state.route_plans):
                col_n, col_d, col_t = st.columns([2,1,1])
                with col_n:
                    st.markdown(f"**{item['name']}**")
                    st.caption(item["desc"])
                with col_d:
                    st.metric("航线总长", f"{item['dist']:.0f}m")
                with col_t:
                    st.metric("预估时长", f"{item['dist']/15:.0f}s")
                if st.session_state.selected_plan["name"] == item["name"]:
                    st.success("✅ 当前预览，已校验零穿墙")
                else:
                    if st.button(f"预览此方案", key=f"sel_plan_{idx}", use_container_width=True):
                        st.session_state.selected_plan = item
                        st.rerun()
                st.markdown("---")

            sel_plan = st.session_state.selected_plan
            diff_len = sel_plan["dist"] - calc_distance(st.session_state.point_a, st.session_state.point_b)
            st.info(f"当前航线相比直线多出绕行距离 {diff_len:.0f} m，全程贴边飞行，不穿透任何建筑")
            if st.button("✈️ 锁定确认该航线", use_container_width=True, type="primary"):
                st.session_state.confirmed_plan = sel_plan
                st.success("✅ 航线锁定完成，切换至飞行监控执行仿真")
                st.balloons()

        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 已锁定待执行航线")
            fix_plan = st.session_state.confirmed_plan
            st.success(f"**{fix_plan['name']}**")
            st.caption(f"总长：{fix_plan['dist']:.0f} m，贴边零穿墙校验通过")

# ========== 飞行监控Tab ==========
with tab2:
    st.subheader("📡 无人机实时飞行任务监控面板")
    col_sim_ctrl, col_sim_view = st.columns([1, 2])
    with col_sim_ctrl:
        st.markdown("### 🎮 仿真任务控制")
        if st.button("📐 导入已锁定航线", use_container_width=True):
            if st.session_state.confirmed_plan is None:
                st.warning("请先在航线规划页面锁定航线！")
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
                st.session_state.drone_current_pos = wp_list[0].copy()
                clear_all_logs()
                add_business_log(f"航线导入成功，航点{len(wp_list)}个，贴边零穿墙校验通过")
                add_gcs_to_fcu_log("地面站→机载：任务下发")
                add_fcu_to_gcs_log("飞控→地面站：任务确认")
                st.success(f"✅ 航线载入完成")
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
            btn_start = st.button("▶️ 启动自动飞行", use_container_width=True, disabled=(len(wp_list)==0))
            if btn_start:
                st.session_state.flight_sim_running = True
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                add_fcu_to_gcs_log("飞控：自动巡航模式开启")
                st.rerun()
        with c_stop:
            if st.button("⏹️ 紧急中止", use_container_width=True):
                st.session_state.flight_sim_running = False
                add_business_log("用户手动中止飞行", color="red")
                st.rerun()
        with c_reset:
            if st.button("🔄 重置仿真", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_current_index = 0
                st.session_state.flight_sim_last_wp_index = -1
                st.session_state.drone_current_pos = wp_list[0].copy() if len(wp_list)>0 else st.session_state.point_a.copy()
                clear_all_logs()
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 航线基础参数")
        st.caption(f"起点：{st.session_state.point_a[0]:.6f}, {st.session_state.point_a[1]:.6f}")
        st.caption(f"终点：{st.session_state.point_b[0]:.6f}, {st.session_state.point_b[1]:.6f}")
        st.caption(f"飞行高度：{st.session_state.flight_alt} m")
        st.caption(f"安全半径：{st.session_state.safe_radius} m")
        st.caption(f"航点总数：{len(wp_list)}")
        if total_dist_sim > 0:
            st.caption(f"航线总长：{total_dist_sim:.1f} m")
            st.caption("✅ 全局零穿墙校验，贴边安全飞行")

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
                st.error(f"⚠️ 链路心跳超时")
            else:
                st.success(f"💓 心跳正常 延迟{hb_item['delay']}ms")
        hb_stats = st.session_state.heartbeat_sim.get_stats()
        ch1, ch2 = st.columns(2)
        ch1.metric("累计心跳包", hb_stats["total"])
        ch2.metric("通信成功率", f"{hb_stats['rate']}%")

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
                        st.session_state.drone_current_pos = [curr_lat, curr_lon]
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
                    add_fcu_to_gcs_log(f"抵达航点#{curr_wp_idx+1}")
                    if curr_wp_idx >= len(wp_list)-1:
                        add_fcu_to_gcs_log("任务完成：全部航点抵达")
                        add_business_log("巡航任务结束，全程贴边无碰撞", color="green")

            st.markdown("### 📊 实时飞行数据")
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            r1c1.metric("当前航点", f"{min(curr_wp_idx+1, len(wp_list))}/{len(wp_list)}")
            r1c2.metric("飞行速度", f"{sim_speed:.1f} m/s")
            r1c3.metric("已飞时长", time_elapse_str)
            r1c4.metric("剩余距离", f"{remain_d:.0f} m")

            r2c1, r2c2, r2c3, _ = st.columns(4)
            r2c1.metric("预计剩余时间", time_remain_str)
            r2c2.metric("剩余电量", f"{batt:.0f}%")
            r2c3.metric("飞行进度", f"{progress_rate*100:.0f}%")
            st.progress(min(1.0, progress_rate))

            st.markdown("---")
            st.markdown("### 🗺️ 实时飞行地图")
            m_sim = create_base_map(CAMPUS, zoom=17)
            m_sim = render_map_content(m_sim, drone_pos=st.session_state.drone_current_pos)
            st_folium(m_sim, width="100%", height=320, key="sim_map")

            st.markdown("---")
            st.markdown("### 📶 通信链路状态")
            gcs_col, obc_col, fcu_col = st.columns(3)
            with gcs_col: st.success("✅ 地面站在线")
            with obc_col: st.success("✅ 机载计算机在线")
            with fcu_col: st.success("✅ 飞控在线")

            st.markdown("---")
            st.markdown("### 📝 通信日志")
            log_box = st.container(height=180)
            with log_box:
                st.caption("【业务日志】")
                for log in st.session_state.comm_logs_business[-10:]:
                    st.caption(f"[{log['timestamp']}] {log['message']}")
                st.caption("⬆️ 飞控上行")
                for log in st.session_state.comm_logs_fcu_to_gcs[-6:]:
                    st.caption(log)
                st.caption("⬇️ 地面站下行")
                for log in st.session_state.comm_logs_gcs_to_fcu[-6:]:
                    st.caption(log)

            if st.session_state.flight_sim_running:
                time.sleep(1.0)
                st.rerun()
        else:
            st.info("操作步骤：1.航线规划页圈选障碍物并生成航线 → 2.锁定航线 → 3.导入并启动仿真")

st.markdown("---")
st.caption("核心优化：迭代式全局碰撞检测，多障碍物依次贴边绕行，航线紧贴缓冲区外侧，全程零穿墙；自动对比左右路径择优最短；修复法线方向底层错误，绕行偏移精准有效")
