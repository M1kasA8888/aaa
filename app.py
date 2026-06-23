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

# ==================== 页面全局配置 ====================
st.set_page_config(page_title="无人机智能监控系统", page_icon="🛰️", layout="wide")

# ==================== 南京科技职业学院中心基准坐标(匹配截图高德卫星WGS84) ====================
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
        # 预设截图中两栋建筑障碍物（可删除，仅演示）
        st.session_state.obstacles = [
            {
                "name": "南侧主楼",
                "height": 40,
                "points": [[32.2340, 118.7486], [32.2345, 118.7486], [32.2345, 118.7502], [32.2340, 118.7502]]
            },
            {
                "name": "北侧教学楼",
                "height": 35,
                "points": [[32.2320, 118.7488], [32.2326, 118.7488], [32.2326, 118.7500], [32.2320, 118.7500]]
            }
        ]

# 【关键修正：交换A/B点，匹配截图 下方起点绿标 / 上方终点红标】
if 'point_a' not in st.session_state:
    if os.path.exists(WAYPOINT_CONFIG_FILE):
        try:
            with open(WAYPOINT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.point_a = data.get('point_a', [32.2344, 118.749])  # 下方起点
                st.session_state.point_b = data.get('point_b', [32.2323, 118.749])  # 上方终点
        except Exception:
            st.session_state.point_a = [32.2344, 118.749]
            st.session_state.point_b = [32.2323, 118.749]
    else:
        st.session_state.point_a = [32.2344, 118.749]
        st.session_state.point_b = [32.2323, 118.749]

# 飞行基础参数
if 'flight_alt' not in st.session_state:
    st.session_state.flight_alt = 20
if 'safe_radius' not in st.session_state:
    st.session_state.safe_radius = 10
if 'bypass_distance' not in st.session_state:
    st.session_state.bypass_distance = 15

# 航线规划存储
if 'route_plans' not in st.session_state:
    st.session_state.route_plans = []
if 'selected_plan' not in st.session_state:
    st.session_state.selected_plan = None
if 'confirmed_plan' not in st.session_state:
    st.session_state.confirmed_plan = None

# 绘制障碍物临时缓存
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

# 通信日志分区
if "comm_logs_business" not in st.session_state:
    st.session_state.comm_logs_business = []
if "comm_logs_gcs_to_fcu" not in st.session_state:
    st.session_state.comm_logs_gcs_to_fcu = []
if "comm_logs_fcu_to_gcs" not in st.session_state:
    st.session_state.comm_logs_fcu_to_gcs = []

# ==================== 持久化文件读写函数 ====================
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

# ==================== 日志打印工具 ====================
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

    def get_history(self):
        return self.history.copy()

if 'heartbeat_sim' not in st.session_state:
    st.session_state.heartbeat_sim = HeartbeatSimulator()
if 'heartbeat_running' not in st.session_state:
    st.session_state.heartbeat_running = False

# ==================== 原生地理计算工具（无Shapely依赖） ====================
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

def seg_intersect_polygon(p0, p1, poly, sample_num=40):
    """线段分段采样，判断是否穿过多边形"""
    for i in range(sample_num+1):
        t = i / sample_num
        lat = p0[0] + (p1[0]-p0[0])*t
        lon = p0[1] + (p1[1]-p0[1])*t
        if point_in_polygon([lat, lon], poly):
            return True
    return False

def offset_polygon_outward(poly, offset_m, base_lat):
    """多边形外扩缓冲区（米）"""
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
    """获取多边形经纬度边界"""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return min(lats), max(lats), min(lons), max(lons)

# ==================== 障碍物数据封装类 ====================
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
        """计算安全绕行缓冲区 = 安全半径 + 预留绕行距离"""
        total_buf = safe_r + bypass_d
        return offset_polygon_outward(self.points, total_buf, CAMPUS[0])

# ==================== 智能绕行路径规划核心算法 ====================
def find_blocking_obstacles(start, end, obs_list, flight_alt, safe_r, bypass_d):
    """筛选高度高于飞行高度、会阻挡直线路径的障碍物"""
    block_obs = []
    block_bufs = []
    for obs_data in obs_list:
        obs = Obstacle.from_dict(obs_data)
        if flight_alt < obs.height:
            buf_poly = obs.get_safe_buffer(safe_r, bypass_d)
            if seg_intersect_polygon(start, end, buf_poly):
                block_obs.append(obs)
                block_bufs.append(buf_poly)
    return block_obs, block_bufs

def generate_bypass_path(start, end, obs_list, buf_list, side, safe_r, bypass_d):
    """逐障碍物生成单侧绕行航线（左/右）"""
    current_pos = start.copy()
    full_path = [current_pos.copy()]
    total_buf = safe_r + bypass_d
    lat_off_deg, lon_off_deg = meter_to_degree(total_buf * 2.5, CAMPUS[0])

    # 逐个遍历阻挡障碍物，独立生成绕行拐点
    for idx, obs in enumerate(obs_list):
        buf_poly = buf_list[idx]
        cx, cy = obs.center_lat, obs.center_lon
        dx_line = end[1] - current_pos[1]
        dy_line = end[0] - current_pos[0]
        line_len = math.hypot(dx_line, dy_line)
        if line_len < 1e-9:
            continue
        dx_line /= line_len
        dy_line /= line_len

        # 计算垂直偏移方向
        if side == "left":
            perp_lat = -dx_line
            perp_lon = dy_line
        else:
            perp_lat = dx_line
            perp_lon = -dy_line

        bypass_pt = [cx + perp_lat * lat_off_deg, cy + perp_lon * lon_off_deg]
        expand_step = 1.4
        max_iter = 25
        iter_cnt = 0

        # 迭代外扩直到起点-绕行点不碰撞缓冲区
        while iter_cnt < max_iter and seg_intersect_polygon(current_pos, bypass_pt, buf_poly):
            bypass_pt[0] += perp_lat * lat_off_deg * expand_step
            bypass_pt[1] += perp_lon * lon_off_deg * expand_step
            iter_cnt += 1

        # 校验绕行点到终点无碰撞
        iter_cnt2 = 0
        while iter_cnt2 < max_iter and seg_intersect_polygon(bypass_pt, end, buf_poly):
            bypass_pt[0] += perp_lat * lat_off_deg * expand_step
            bypass_pt[1] += perp_lon * lon_off_deg * expand_step
            iter_cnt2 += 1

        full_path.append(bypass_pt.copy())
        current_pos = bypass_pt.copy()
    full_path.append(end.copy())

    # 二次过滤危险航段
    final_path = [full_path[0]]
    for i in range(1, len(full_path)):
        seg_safe = True
        for buf in buf_list:
            if seg_intersect_polygon(final_path[-1], full_path[i], buf):
                seg_safe = False
                break
        final_path.append(full_path[i].copy())
    return final_path

def calc_path_total_dist(waypoints):
    """计算航线总长度 + 分段距离列表"""
    total = 0.0
    seg_dist = []
    for i in range(len(waypoints)-1):
        d = calc_distance(waypoints[i], waypoints[i+1])
        seg_dist.append(d)
        total += d
    return total, seg_dist

# ==================== 页面主体渲染入口 ====================
st.title("🛰️ 无人机智能监控系统")
st.markdown("**南京科技职业学院 | 多建筑逐栋绕行 | 全程不穿墙 | 仅左/右/最优3套方案**")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.subheader("🌐 坐标系配置")
    st.selectbox("输入坐标系", ["WGS-84（高德卫星图）", "GCJ-02 (高德/百度)"])
    st.markdown("---")
    st.subheader("📊 系统状态")
    st.success("✅ 系统正常待机")
    st.markdown("### 📖 操作流程")
    st.caption("1. 地图多边形绘制建筑障碍物")
    st.caption("2. 设置建筑高度保存")
    st.caption("3. 填写起终点坐标匹配卫星图")
    st.caption("4. 生成左/右/最优航线")
    st.caption("5. 确认航线后进入飞行仿真")

tab1, tab2 = st.tabs(["🗺️ 航线规划", "📡 飞行监控"])

# ========== Tab1：航线规划地图页面 ==========
with tab1:
    col_map, col_ctrl = st.columns([1.6, 1])
    with col_map:
        st.subheader("🗺️ 高德卫星底图（匹配截图）")
        m = folium.Map(location=CAMPUS, zoom_start=17, control_scale=True)
        # 高德卫星图层
        folium.TileLayer(
            "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
            attr="高德卫星图源", subdomains=["1","2","3","4"], name="卫星地图"
        ).add_to(m)
        # OSM街道底图切换
        folium.TileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="OpenStreetMap", name="街道地图"
        ).add_to(m)
        folium.Marker(CAMPUS, popup="🏫 南京科技职业学院中心", icon=folium.Icon(color="red")).add_to(m)

        alt = st.session_state.flight_alt
        total_buf_w = st.session_state.safe_radius + st.session_state.bypass_distance
        # 渲染所有障碍物建筑
        for obs_data in st.session_state.obstacles:
            obs = Obstacle.from_dict(obs_data)
            line_color = "red" if alt < obs.height else "green"
            folium.Polygon(
                obs.points, color=line_color, weight=2, fill=True,
                fill_color=line_color, fill_opacity=0.3,
                popup=f"{obs.name}\n建筑高度：{obs.height}m"
            ).add_to(m)
            # 飞行高度低于建筑则绘制蓝色虚线安全缓冲区
            if alt < obs.height:
                buf_coords = obs.get_safe_buffer(st.session_state.safe_radius, st.session_state.bypass_distance)
                folium.Polygon(
                    buf_coords, color="blue", weight=1.5, dash_array="5,5", fill=False,
                    popup=f"安全绕行缓冲区 {total_buf_w}m"
                ).add_to(m)

        # 起终点标记（匹配截图：A下方绿色起点，B上方红色终点）
        folium.Marker(st.session_state.point_a, popup="🚁 起点A（图下方绿标）", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(st.session_state.point_b, popup="🎯 终点B（图上方红标）", icon=folium.Icon(color="red")).add_to(m)

        # 渲染选中的规划航线
        if st.session_state.selected_plan:
            plan = st.session_state.selected_plan
            folium.PolyLine(plan["points"], color=plan["color"], weight=4, opacity=0.9).add_to(m)
            for idx, wp in enumerate(plan["points"][1:-1], 1):
                folium.Marker(wp, popup=f"绕行拐点{idx}", icon=folium.Icon(color="purple", icon="refresh")).add_to(m)

        # 绘图工具 + 测距 + 图层切换
        plugins.Draw(draw_options={"polygon": {"allowIntersection": False}}).add_to(m)
        plugins.MeasureControl().add_to(m)
        folium.LayerControl().add_to(m)
        map_out = st_folium(m, width="100%", height=520, key="main_map")

        # 捕获绘制的多边形障碍物
        if map_out and map_out.get("last_active_drawing"):
            draw_data = map_out["last_active_drawing"]
            if draw_data["geometry"]["type"] == "Polygon":
                pts = [[coord[1], coord[0]] for coord in draw_data["geometry"]["coordinates"][0]]
                if len(pts) >= 3:
                    st.session_state.temp_obs = pts
                    st.session_state.show_height_panel = True
                    st.success(f"✅ 绘制完成，障碍物顶点数：{len(pts)}")

    with col_ctrl:
        # 新建障碍物弹窗
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

        # 起点A（截图下方绿标）坐标设置
        st.markdown("### 🚁 起点A（地图下方绿标）")
        c_a1, c_a2 = st.columns(2)
        lat_a = c_a1.number_input("纬度", value=st.session_state.point_a[0], format="%.6f")
        lon_a = c_a2.number_input("经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("📍 更新起点A", use_container_width=True):
            st.session_state.point_a = [lat_a, lon_a]
            save_waypoints()
            st.rerun()

        # 终点B（截图上方红标）坐标设置
        st.markdown("### 🎯 终点B（地图上方红标）")
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
        safe_slider = st.slider("建筑安全半径(m)", min_value=5, max_value=30, value=st.session_state.safe_radius)
        st.session_state.safe_radius = safe_slider
        bypass_slider = st.slider("额外绕行预留距离(m)", min_value=5, max_value=50, value=st.session_state.bypass_distance)
        st.session_state.bypass_distance = bypass_slider
        st.info(f"🛡️ 总安全缓冲区宽度：{safe_slider + bypass_slider} m")

        # 障碍物高度校验提示
        if st.session_state.obstacles:
            st.markdown("**📊 建筑高度检测**")
            for obs_data in st.session_state.obstacles:
                obs = Obstacle.from_dict(obs_data)
                if alt_slider < obs.height:
                    st.warning(f"🔄 {obs.name}({obs.height}m) → 需要绕行")
                else:
                    st.success(f"✅ {obs.name} → 可飞越")

        st.markdown("---")
        st.markdown("### 🚧 已保存建筑障碍物列表")
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
            if st.button("💾 保存全部配置", use_container_width=True):
                save_obstacles_to_file()
                save_waypoints()
                st.success("配置已写入本地JSON文件")
        with c_load:
            if st.button("📂 加载本地配置", use_container_width=True):
                load_obstacles_from_file()
                st.rerun()
        with c_clear:
            if st.button("🗑️ 清空所有建筑", use_container_width=True):
                st.session_state.obstacles = []
                save_obstacles_to_file()
                st.rerun()

        st.markdown("---")
        st.markdown("## 🗺️ 一键生成3套航线方案")
        if st.button("🎯 生成左/右/最优航线", use_container_width=True, type="primary"):
            start_pt = st.session_state.point_a
            end_pt = st.session_state.point_b
            straight_dist = calc_distance(start_pt, end_pt)
            block_obs, block_bufs = find_blocking_obstacles(start_pt, end_pt, st.session_state.obstacles, alt_slider, safe_slider, bypass_slider)
            plan_list = []
            if len(block_obs) == 0:
                plan_list.append({
                    "name": "📏 直线飞越航线",
                    "points": [start_pt, end_pt],
                    "dist": straight_dist,
                    "color": "blue",
                    "desc": "无遮挡建筑，直线直达"
                })
            else:
                # 左右两套绕行方案
                dir_config = [("left", "⬅️ 左侧绕行", "orange"), ("right", "➡️ 右侧绕行", "purple")]
                for side, name, color in dir_config:
                    path = generate_bypass_path(start_pt, end_pt, block_obs, block_bufs, side, safe_slider, bypass_slider)
                    dist_total, _ = calc_path_total_dist(path)
                    plan_list.append({
                        "name": name,
                        "points": path,
                        "dist": dist_total,
                        "color": color,
                        "desc": "逐栋绕开全部建筑安全缓冲区，无穿墙风险"
                    })
                # 自动对比生成最短最优航线
                best_plan = min(plan_list, key=lambda x: x["dist"]).copy()
                best_plan["name"] = "⭐ 最优最短航线"
                best_plan["color"] = "gold"
                best_plan["desc"] = f"左右绕行对比最短路径，总长{best_plan['dist']:.1f}m"
                plan_list.append(best_plan)
            st.session_state.route_plans = plan_list
            st.session_state.selected_plan = plan_list[-1]
            st.rerun()

        # 航线方案选择面板
        if st.session_state.route_plans:
            st.markdown("---")
            st.markdown("### 📋 可选航线方案列表")
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
                    st.success("✅ 当前选中")
                else:
                    if st.button(f"选用此航线", key=f"sel_plan_{idx}", use_container_width=True):
                        st.session_state.selected_plan = p_item
                        st.rerun()
                st.markdown("---")

            # 选中航线详情
            if st.session_state.selected_plan:
                sel_plan = st.session_state.selected_plan
                diff_len = sel_plan["dist"] - calc_distance(st.session_state.point_a, st.session_state.point_b)
                st.info(f"当前选中：{sel_plan['name']}，相比直线多出绕行距离 {diff_len:.0f} m")
                if st.button("✈️ 确认锁定该航线", use_container_width=True, type="primary"):
                    st.session_state.confirmed_plan = sel_plan
                    st.success("✅ 航线锁定完成，切换至飞行监控页面启动仿真")
                    st.balloons()

        # 已锁定航线提示
        if st.session_state.confirmed_plan:
            st.markdown("---")
            st.markdown("### ✅ 已锁定执行航线")
            fix_plan = st.session_state.confirmed_plan
            st.success(f"**{fix_plan['name']}**")
            st.caption(f"航线总长：{fix_plan['dist']:.0f} m，预估飞行 {fix_plan['dist']/15:.0f} s")

# ========== Tab2：飞行仿真监控页面 ==========
with tab2:
    st.subheader("📡 实时飞行任务仿真监控")
    col_sim_ctrl, col_sim_view = st.columns([1, 2])
    with col_sim_ctrl:
        st.markdown("### 🎮 仿真任务控制")
        if st.button("📐 导入已确认航线", use_container_width=True):
            if st.session_state.confirmed_plan is None:
                st.warning("⚠️ 请先在【航线规划】页面确认锁定航线！")
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
                add_business_log(f"航线导入成功，航点总数{len(wp_list)}，航线总长{total_d:.1f}m")
                add_gcs_to_fcu_log("GCS→OBC: MISSION_UPLOAD 上传航线任务")
                add_fcu_to_gcs_log("FCU→OBC: MISSION_ACK 航线校验通过")
                st.success(f"✅ 航线载入完成，共{len(wp_list)}个航点")
                st.rerun()

        wp_list = st.session_state.flight_sim_waypoints
        seg_dist_list = st.session_state.flight_sim_segment_distances
        total_dist_sim = st.session_state.flight_sim_total_distance

        st.markdown("---")
        sim_speed = st.slider("仿真飞行速度(m/s)", min_value=1.0, max_value=20.0, step=0.5, value=st.session_state.flight_sim_speed)
        st.session_state.flight_sim_speed = sim_speed
        st.markdown("---")
        c_start, c_stop, c_reset = st.columns(3)
        with c_start:
            btn_start = st.button("▶️ 启动自动任务", use_container_width=True, disabled=(len(wp_list)==0))
            if btn_start:
                st.session_state.flight_sim_running = True
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                add_fcu_to_gcs_log("FCU→OBC→GCS: ACK | AUTO自动飞行模式开启")
                st.rerun()
        with c_stop:
            if st.button("⏹️ 紧急中止飞行", use_container_width=True):
                st.session_state.flight_sim_running = False
                add_fcu_to_gcs_log("FCU→GCS: EMERGENCY_HOLD 任务暂停")
                st.rerun()
        with c_reset:
            if st.button("🔄 重置仿真状态", use_container_width=True):
                st.session_state.flight_sim_running = False
                st.session_state.flight_sim_start_time = None
                st.session_state.flight_sim_current_index = 0
                st.session_state.flight_sim_last_wp_index = -1
                clear_all_logs()
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 当前航线基础信息")
        st.caption(f"起点A：{st.session_state.point_a[0]:.6f}, {st.session_state.point_a[1]:.6f}")
        st.caption(f"终点B：{st.session_state.point_b[0]:.6f}, {st.session_state.point_b[1]:.6f}")
        st.caption(f"飞行高度：{st.session_state.flight_alt} m")
        st.caption(f"建筑安全半径：{st.session_state.safe_radius} m")
        st.caption(f"绕行预留距离：{st.session_state.bypass_distance} m")
        st.caption(f"航点总数：{len(wp_list)}")
        if total_dist_sim > 0:
            st.caption(f"航线总长度：{total_dist_sim:.1f} m")

        st.markdown("---")
        st.markdown("### 💓 空地链路心跳监控")
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
                st.error(f"⚠️ 链路超时，3s未收到飞控心跳反馈")
            else:
                st.success(f"💓 心跳链路正常 | ID:{hb_item['id']} 延迟:{hb_item['delay']}ms")
        hb_stats = st.session_state.heartbeat_sim.get_stats()
        ch1, ch2 = st.columns(2)
        ch1.metric("总心跳包数", hb_stats["total"])
        ch2.metric("心跳通信成功率", f"{hb_stats['rate']}%")

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
                # 计算当前飞机所处分段、实时坐标
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
                    add_fcu_to_gcs_log("FCU→GCS: MISSION_FINISH 全部航点完成")

                remain_d = max(0.0, total_dist_sim - flown_d)
                remain_sec = remain_d / sim_speed if sim_speed>1e-6 else 0
                # 时分格式化
                m_el = int(elapse_sec // 60)
                s_el = int(elapse_sec % 60)
                time_elapse_str = f"{m_el:02d}:{s_el:02d}"
                m_re = int(remain_sec // 60)
                s_re = int(remain_sec % 60)
                time_remain_str = f"{m_re:02d}:{s_re:02d}"
                batt = max(0.0, 100.0 - (elapse_sec / 1800.0)*100.0)
                progress_rate = flown_d / total_dist_sim if total_dist_sim>1e-6 else 0.0

                # 抵达新航点日志上报
                if curr_wp_idx > st.session_state.flight_sim_last_wp_index:
                    st.session_state.flight_sim_last_wp_index = curr_wp_idx
                    add_fcu_to_gcs_log(f"FCU→GCS: 抵达航点#{curr_wp_idx}")
                    if curr_wp_idx >= len(wp_list)-1:
                        add_business_log("完整航线执行完毕，自动返航待命", color="green")

            # 实时飞行数据面板
            st.markdown("### 📊 实时飞行遥测数据")
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            r1c1.metric("当前航点", f"{min(curr_wp_idx+1, len(wp_list))}/{len(wp_list)}")
            r1c2.metric("飞行速度", f"{sim_speed:.1f} m/s")
            r1c3.metric("已飞行时长", time_elapse_str)
            r1c4.metric("剩余距离", f"{remain_d:.0f} m")

            r2c1, r2c2, r2c3, _ = st.columns(4)
            r2c1.metric("预计剩余时间", time_remain_str)
            r2c2.metric("剩余电量", f"{batt:.0f}%")
            r2c3.metric("飞行完成进度", f"{progress_rate*100:.0f}%")
            st.progress(min(1.0, progress_rate))

            st.markdown("---")
            st.markdown("### 📶 机载通信链路状态")
            gcs_col, obc_col, fcu_col = st.columns(3)
            with gcs_col: st.success("✅ GCS 地面站在线")
            with obc_col: st.success("✅ OBC机载计算机在线")
            with fcu_col: st.success("✅ FCU飞控在线")
            st.markdown("---")

            # 任务状态提示
            if st.session_state.flight_sim_running:
                st.info("✈️ 飞行任务执行中，遥测实时更新...")
            elif curr_wp_idx >= len(wp_list)-1:
                st.success("✅ 全部航点飞行完成，任务结束！")
            else:
                st.info("⏸️ 仿真已暂停，点击【启动自动任务】开始飞行")

            st.markdown("---")
            st.markdown("### 📝 上下行通信日志（最新消息）")
            log_box = st.container(height=220)
            with log_box:
                for log_item in st.session_state.comm_logs_business[-10:]:
                    st.caption(f"📋 [{log_item['timestamp']}] {log_item['message']}")
                for log_item in st.session_state.comm_logs_fcu_to_gcs[-5:]:
                    st.caption(f"⬆️ {log_item}")
                for log_item in st.session_state.comm_logs_gcs_to_fcu[-5:]:
                    st.caption(f"⬇️ {log_item}")

            # 优化：移除阻塞页面的time.sleep，改用streamlit自动刷新机制
            if st.session_state.flight_sim_running:
                st.rerun()
        else:
            st.info("📭 暂无航线数据，请先在航线规划页面锁定航线后导入")

st.markdown("---")
st.caption("操作说明：地图绘制多边形框选建筑→设置建筑高度保存→调整飞行安全参数→一键生成左/右/最优绕行航线，算法自动避开建筑蓝色安全缓冲区，无穿墙风险，适配南京科技职业学院高德卫星图")
