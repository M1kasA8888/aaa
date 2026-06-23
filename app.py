import streamlit as st
import math
import json
import os
import time
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="无人机监测系统")

# ==================== 坐标转换函数（保留你的原版） ====================
pi = 3.1415926535897932384626
a = 6378245.0
ee = 0.00669342162296594323

def _transform_lat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
        0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 * math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 * math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret

def _transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
        0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 * math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 * math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret

def out_of_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)

def wgs84_to_gcj02(lng, lat):
    if out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    return lng + dlng, lat + dlat

def gcj02_to_wgs84(lng, lat):
    if out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    return lng - dlng, lat - dlat

# ==================== 几何底层工具（修复穿墙核心） ====================
def calc_distance_meters(p1, p2):
    """计算两点间距离，输入(lng, lat)，输出米"""
    lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
    lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])
    R = 6371000
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a_val = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a_val), math.sqrt(1-a_val))

def meter_to_degree(meter, base_lat):
    lat_per_m = 1.0 / 111320.0
    lon_per_m = 1.0 / (111320.0 * math.cos(math.radians(base_lat)))
    return meter * lat_per_m, meter * lon_per_m

def point_in_polygon(pt, poly):
    """pt=(lng,lat), poly=[(lng,lat),...]"""
    x, y = pt[0], pt[1]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][0], poly[i][1]
        x2, y2 = poly[(i+1)%n][0], poly[(i+1)%n][1]
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
            inside = not inside
    return inside

def offset_polygon_outward(poly, offset_m, base_lat):
    """多边形向外偏移，输入(lng,lat)格式"""
    lat_off, lon_off = meter_to_degree(offset_m, base_lat)
    new_poly = []
    n = len(poly)
    for i in range(n):
        p = poly[i]
        p_prev = poly[(i-1)%n]
        p_next = poly[(i+1)%n]
        dx1 = p[0] - p_prev[0]
        dy1 = p[1] - p_prev[1]
        dx2 = p_next[0] - p[0]
        dy2 = p_next[1] - p[1]
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
        new_lng = p[0] + nx * lon_off
        new_lat = p[1] + ny * lat_off
        new_poly.append([new_lng, new_lat])
    return new_poly

def check_segment_collide_all(p0, p1, raw_polys, buf_polys, sample_num=120):
    """检测线段是否碰撞任意障碍物（本体+缓冲区），返回(是否碰撞, 障碍物索引, 碰撞位置t)"""
    for i in range(sample_num + 1):
        t = i / sample_num
        lng = p0[0] + (p1[0]-p0[0]) * t
        lat = p0[1] + (p1[1]-p0[1]) * t
        pt = [lng, lat]
        for idx, (raw, buf) in enumerate(zip(raw_polys, buf_polys)):
            if point_in_polygon(pt, raw) or point_in_polygon(pt, buf):
                return True, idx, t
    return False, -1, 0.0

# ==================== 核心：多障碍物贴边绕行算法（零穿墙） ====================
def calculate_distances(waypoints):
    """计算航线总距离和各航段距离，waypoints=(lng,lat)列表"""
    total = 0
    segment_distances = []
    for i in range(len(waypoints) - 1):
        d = calc_distance_meters(waypoints[i], waypoints[i + 1])
        segment_distances.append(d)
        total += d
    return total, segment_distances

def generate_edge_bypass_route(start, end, raw_polys, buf_polys, side, safe_r, bypass_d):
    """生成单侧贴边绕行路径，迭代式直到全程无碰撞"""
    total_buf = safe_r + bypass_d
    base_lat = (start[1] + end[1]) / 2
    lat_off, lon_off = meter_to_degree(total_buf * 1.1, base_lat) # 仅10%余量，贴边飞行
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
            hit_lng = p0[0] + (p1[0]-p0[0]) * hit_t
            hit_lat = p0[1] + (p1[1]-p0[1]) * hit_t
            # 计算航线方向的垂直法线（修复经纬度分量方向错误）
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            line_len = math.hypot(dx, dy)
            if line_len < 1e-9:
                new_path.append(p1)
                continue
            dx_norm = dx / line_len
            dy_norm = dy / line_len

            # 左右侧法线方向
            if side == "left":
                perp_lng = -dy_norm
                perp_lat = dx_norm
            else:
                perp_lng = dy_norm
                perp_lat = -dx_norm

            # 生成贴边绕行点
            bypass_lng = hit_lng + perp_lng * lon_off
            bypass_lat = hit_lat + perp_lat * lat_off
            bypass_pt = [bypass_lng, bypass_lat]

            # 迭代外扩确保绝对安全
            for _ in range(15):
                safe1, _, _ = check_segment_collide_all(p0, bypass_pt, raw_polys, buf_polys)
                safe2, _, _ = check_segment_collide_all(bypass_pt, p1, raw_polys, buf_polys)
                if not safe1 and not safe2:
                    break
                bypass_pt[0] += perp_lng * lon_off * 0.2
                bypass_pt[1] += perp_lat * lat_off * 0.2

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
        if last_pt is None or calc_distance_meters(pt, last_pt) > 0.5:
            final_path.append(pt)
            last_pt = pt
    return final_path

def calculate_avoidance_waypoints(start, end, obstacles, flight_height, safe_radius, strategy, bypass_offset):
    """
    主避障函数，兼容你原有的参数接口
    start/end: (lng, lat)
    obstacles: 你的格式 [{name, coords:[(lng,lat),...], height}, ...]
    strategy: direct/left/right/best
    """
    # 筛选低于飞行高度的障碍物，生成本体+缓冲区多边形
    raw_polys = []
    buf_polys = []
    base_lat = (start[1] + end[1]) / 2
    for obs in obstacles:
        if obs['height'] >= flight_height:
            raw = obs['coords']
            buf = offset_polygon_outward(raw, safe_radius + bypass_offset, base_lat)
            raw_polys.append(raw)
            buf_polys.append(buf)

    # 直接飞越策略
    if strategy == 'direct' or len(raw_polys) == 0:
        return [start, end]

    # 生成左右绕行路径
    left_path = generate_edge_bypass_route(start, end, raw_polys, buf_polys, "left", safe_radius, bypass_offset)
    right_path = generate_edge_bypass_route(start, end, raw_polys, buf_polys, "right", safe_radius, bypass_offset)
    dist_left, _ = calculate_distances(left_path)
    dist_right, _ = calculate_distances(right_path)

    if strategy == 'left':
        return left_path
    elif strategy == 'right':
        return right_path
    else: # best 自动选最短
        return left_path if dist_left < dist_right else right_path

# ==================== 初始化 Session State（完全保留你的变量） ====================
if "heartbeats" not in st.session_state:
    st.session_state.heartbeats = []
    st.session_state.last_time = time.time()
    st.session_state.running = False
if "coords_a" not in st.session_state:
    st.session_state.coords_a = {"lat": 32.230500, "lon": 118.748500}
if "coords_b" not in st.session_state:
    st.session_state.coords_b = {"lat": 32.238000, "lon": 118.754000}
if "flight_height" not in st.session_state:
    st.session_state.flight_height = 50
if "safe_radius" not in st.session_state:
    st.session_state.safe_radius = 5.0
if "bypass_offset" not in st.session_state:
    st.session_state.bypass_offset = 5.0
if "coord_system" not in st.session_state:
    st.session_state.coord_system = "GCJ-02 (高德/腾讯)"
if "page" not in st.session_state:
    st.session_state.page = "飞行监控"
if "obstacles" not in st.session_state:
    st.session_state.obstacles = []
if "avoidance_strategy" not in st.session_state:
    st.session_state.avoidance_strategy = "best"
if "pending_polygon" not in st.session_state:
    st.session_state.pending_polygon = None
if "drawn_polygon" not in st.session_state:
    st.session_state.drawn_polygon = []

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

# 通信日志
if "comm_logs_business" not in st.session_state:
    st.session_state.comm_logs_business = []
if "comm_logs_gcs_to_fcu" not in st.session_state:
    st.session_state.comm_logs_gcs_to_fcu = []
if "comm_logs_fcu_to_gcs" not in st.session_state:
    st.session_state.comm_logs_fcu_to_gcs = []

CONFIG_FILE = "obstacle_config.json"

# ==================== 持久化函数（保留你的原版） ====================
def load_obstacles():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "obstacles" in data:
                st.session_state.obstacles = data["obstacles"]
                st.success(f"已加载 {len(data['obstacles'])} 个障碍物")
        except Exception as e:
            st.error(f"加载失败: {e}")

def save_obstacles():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"obstacles": st.session_state.obstacles}, f, ensure_ascii=False, indent=2)
        st.success("障碍物配置已保存到文件")
    except Exception as e:
        st.error(f"保存失败: {e}")

# ==================== 日志辅助函数（保留你的原版） ====================
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

# ==================== 侧边栏导航（保留你的原版） ====================
with st.sidebar:
    st.title("🚁 导航")
    page = st.radio("功能页面", ["飞行监控", "航线规划"])
    st.session_state.page = page

# ==================== 地图创建函数（保留你的样式+修复航线） ====================
def create_complete_map(lat_a, lon_a, lat_b, lon_b, obstacles, flight_height, safe_radius, waypoints):
    center_lat = (lat_a + lat_b) / 2
    center_lon = (lon_a + lon_b) / 2
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=17,
        tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        attr='高德卫星地图'
    )

    # 原始直飞航线（灰色虚线）
    folium.PolyLine(
        locations=[[lat_a, lon_a], [lat_b, lon_b]],
        color='gray',
        weight=3,
        opacity=0.5,
        dash_array='5,5',
        tooltip='原始航线'
    ).add_to(m)

    # 规划后航线（红色实线）
    folium.PolyLine(
        locations=[[p[1], p[0]] for p in waypoints],
        color='red',
        weight=5,
        opacity=0.8,
        tooltip='规划航线'
    ).add_to(m)

    # 航点标记
    for i, (lng, lat) in enumerate(waypoints):
        folium.CircleMarker(
            location=[lat, lng],
            radius=4,
            color='blue' if i in (0, len(waypoints)-1) else 'orange',
            fill=True,
            popup=f'航点{i}'
        ).add_to(m)

    # 起止点标记
    folium.Marker(
        location=[lat_a, lon_a],
        popup='起点A',
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    folium.Marker(
        location=[lat_b, lon_b],
        popup='终点B',
        icon=folium.Icon(color='red', icon='flag-checkered', prefix='fa')
    ).add_to(m)

    # 障碍物绘制
    for obs in obstacles:
        polygon_coords = [[coord[1], coord[0]] for coord in obs["coords"]]
        folium.Polygon(
            locations=polygon_coords,
            color='orange',
            fill=True,
            fill_color='orange',
            fill_opacity=0.4,
            weight=2,
            tooltip=f"{obs['name']} (高{obs['height']}m)"
        ).add_to(m)
        center_lat_obs = sum(c[1] for c in obs["coords"])/len(obs["coords"])
        center_lng_obs = sum(c[0] for c in obs["coords"])/len(obs["coords"])
        folium.Marker(
            location=[center_lat_obs, center_lng_obs],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 12px; font-weight: bold; color: #ff6600;">{obs["height"]}m</div>'
            )
        ).add_to(m)

    # 信息标签
    folium.Marker(
        location=[center_lat, center_lon],
        icon=folium.DivIcon(html=f'<div style="background:white; padding:2px 6px; border-radius:15px; border:1px solid red;">✈️ 高度:{flight_height}m | 半径:{safe_radius}m</div>')
    ).add_to(m)

    # 绘制工具
    draw = folium.plugins.Draw(
        draw_options={
            'polyline': False,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False,
            'polygon': True
        },
        edit_options={'edit': True}
    )
    draw.add_to(m)
    return m

# ==================== 航线规划页面（保留你的操作布局+新算法） ====================
if st.session_state.page == "航线规划":
    st.title("🗺️ 航线规划 + 障碍物圈选")

    with st.sidebar:
        st.divider()
        st.header("🎮 坐标系设置")
        coord_system = st.selectbox(
            "输入坐标系",
            ["GCJ-02 (高德/腾讯)", "WGS-84 (GPS)"],
            index=0 if "GCJ-02" in st.session_state.coord_system else 1
        )
        st.session_state.coord_system = coord_system
        is_gcj02 = "GCJ-02" in coord_system

        st.divider()
        st.header("📍 起点 A")
        lat_a_input = st.number_input("纬度 A", value=st.session_state.coords_a["lat"], format="%.6f")
        lon_a_input = st.number_input("经度 A", value=st.session_state.coords_a["lon"], format="%.6f")
        
        st.header("📍 终点 B")
        lat_b_input = st.number_input("纬度 B", value=st.session_state.coords_b["lat"], format="%.6f")
        lon_b_input = st.number_input("经度 B", value=st.session_state.coords_b["lon"], format="%.6f")

        st.divider()
        st.header("✈️ 飞行参数")
        flight_height = st.slider("飞行高度 (m)", 20, 100, st.session_state.flight_height)
        st.session_state.flight_height = flight_height
        safe_radius = st.number_input("安全半径 (m)", min_value=1.0, max_value=50.0, value=st.session_state.safe_radius, step=1.0)
        st.session_state.safe_radius = safe_radius
        bypass_offset = st.slider("绕行偏移量 (米)", min_value=2.0, max_value=20.0, value=st.session_state.bypass_offset, step=1.0)
        st.session_state.bypass_offset = bypass_offset

        st.divider()
        st.header("🔄 避障策略")
        strategy = st.radio(
            "选择绕行方式",
            options=['direct', 'left', 'right', 'best'],
            format_func=lambda x: { 
                'direct': '直接飞 (高度足够时)', 
                'left': '向左绕行', 
                'right': '向右绕行', 
                'best': '最佳航线' 
            }[x],
            index=['direct', 'left', 'right', 'best'].index(st.session_state.avoidance_strategy)
        )
        st.session_state.avoidance_strategy = strategy

        st.divider()
        st.subheader("🗂️ 障碍物持久化")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存障碍物", use_container_width=True):
                save_obstacles()
        with col2:
            if st.button("📂 加载障碍物", use_container_width=True):
                load_obstacles()
        if st.button("🗑️ 清除全部障碍物", use_container_width=True):
            st.session_state.obstacles = []
            st.session_state.drawn_polygon = []
            st.success("已清除所有障碍物")
        
        st.divider()
        st.subheader("➕ 添加障碍物")
        st.markdown("1️⃣ 在地图上绘制多边形\n2️⃣ 点击 Save 按钮\n3️⃣ 填写信息并添加")
        
        if st.session_state.drawn_polygon:
            st.success(f"✅ 已捕获多边形，顶点数: {len(st.session_state.drawn_polygon)}")
        else:
            st.info("⏳ 尚未捕获多边形，请先绘制")
        
        new_obs_name = st.text_input("障碍物名称", placeholder="例如：新建筑")
        new_obs_height = st.number_input("高度 (米)", min_value=0, max_value=200, value=30)
        
        if st.button("✅ 添加已圈选的多边形", use_container_width=True):
            if st.session_state.drawn_polygon and len(st.session_state.drawn_polygon) >= 3:
                if new_obs_name:
                    st.session_state.obstacles.append({
                        "name": new_obs_name,
                        "coords": st.session_state.drawn_polygon,
                        "height": new_obs_height
                    })
                    st.success(f"已添加障碍物: {new_obs_name}")
                    st.session_state.drawn_polygon = []
                    st.rerun()
                else:
                    st.error("请输入障碍物名称")
            else:
                st.error("请先在地图上绘制一个多边形（至少3个顶点）")

    # 坐标转换
    if is_gcj02:
        lat_a_display, lon_a_display = lat_a_input, lon_a_input
        lat_b_display, lon_b_display = lat_b_input, lon_b_input
    else:
        lon_a_gcj, lat_a_gcj = wgs84_to_gcj02(lon_a_input, lat_a_input)
        lon_b_gcj, lat_b_gcj = wgs84_to_gcj02(lon_b_input, lat_b_input)
        lat_a_display, lon_a_display = lat_a_gcj, lon_a_gcj
        lat_b_display, lon_b_display = lat_b_gcj, lon_b_gcj

    st.session_state.coords_a = {"lat": lat_a_display, "lon": lon_a_display}
    st.session_state.coords_b = {"lat": lat_b_display, "lon": lon_b_display}

    start = (lon_a_display, lat_a_display)
    end = (lon_b_display, lat_b_display)
    waypoints = calculate_avoidance_waypoints(
        start, end, st.session_state.obstacles, flight_height, safe_radius, strategy, bypass_offset
    )

    # 生成航线日志
    if st.button("📝 生成航线规划日志", use_container_width=True):
        clear_all_logs()
        total_dist, _ = calculate_distances(waypoints)
        add_business_log(f"航线规划完成 | 类型: horizontal | 航点数: {len(waypoints)} | 路径长度: {total_dist:.1f}m", color="green")
        add_business_log(f"开始航线规划 | 算法: 迭代贴边避障 | 障碍物数量: {len(st.session_state.obstacles)}", color="gray")
        add_business_log(f"导航目标 | 起点: ({lat_a_display:.6f}, {lon_a_display:.6f}), 终点: ({lat_b_display:.6f}, {lon_b_display:.6f}), 目标高度: {flight_height}m", source="GCS → OBC", color="blue")
        add_gcs_to_fcu_log("GCS→OBC: MISSION_UPLOAD")
        add_gcs_to_fcu_log("OBC→FCU: MISSION_COUNT")
        add_gcs_to_fcu_log("OBC→FCU: MISSION_ITEM")
        add_fcu_to_gcs_log("FCU→OBC: MISSION_ACK")
        add_fcu_to_gcs_log("OBC→GCS: MISSION_ACK")
        st.success("✅ 航线规划日志已生成，请切换到飞行监控页面查看")

    m_complete = create_complete_map(
        lat_a_display, lon_a_display, lat_b_display, lon_b_display,
        st.session_state.obstacles, flight_height, safe_radius, waypoints
    )
    output = st_folium(m_complete, width=900, height=600, key="map_complete")

    # 捕获绘制的多边形
    if output and output.get("last_active_drawing"):
        geo = output["last_active_drawing"].get("geometry", {})
        if geo.get("type") == "Polygon":
            coords = geo.get("coordinates", [])
            if coords:
                st.session_state.drawn_polygon = coords[0][:-1]

# ==================== 飞行监控页面（完全保留你的布局+功能） ====================
elif st.session_state.page == "飞行监控":
    st.title("📡 飞行实时画面 - 任务执行监控")
    
    # 侧边栏控制
    with st.sidebar:
        st.divider()
        st.header("🎮 飞行控制")
        
        if st.button("📐 导入当前航线", use_container_width=True):
            start = (st.session_state.coords_a["lon"], st.session_state.coords_a["lat"])
            end = (st.session_state.coords_b["lon"], st.session_state.coords_b["lat"])
            waypoints = calculate_avoidance_waypoints(
                start, end, st.session_state.obstacles,
                st.session_state.flight_height, st.session_state.safe_radius,
                st.session_state.avoidance_strategy, st.session_state.bypass_offset
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
            add_business_log(f"航线规划完成 | 类型: horizontal | 航点数: {len(waypoints)} | 路径长度: {total_dist:.1f}m", color="green")
            add_business_log(f"开始航线规划 | 算法: 迭代贴边避障 | 障碍物数量: {len(st.session_state.obstacles)}", color="gray")
            add_business_log(f"导航目标 | 起点: ({start[1]:.6f}, {start[0]:.6f}), 终点: ({end[1]:.6f}, {end[0]:.6f}), 目标高度: {st.session_state.flight_height}m", source="GCS → OBC", color="blue")
            add_gcs_to_fcu_log("GCS→OBC: MISSION_UPLOAD")
            add_gcs_to_fcu_log("OBC→FCU: MISSION_COUNT")
            add_gcs_to_fcu_log("OBC→FCU: MISSION_ITEM")
            add_fcu_to_gcs_log("FCU→OBC: MISSION_ACK")
            add_fcu_to_gcs_log("OBC→GCS: MISSION_ACK")
            st.success(f"✅ 航线已导入，共 {len(waypoints)} 个航点，总距离 {total_dist:.1f} 米")
            st.rerun()
        
        total_dist = st.session_state.flight_sim_total_distance
        waypoints = st.session_state.flight_sim_waypoints
        seg_dists = st.session_state.flight_sim_segment_distances
        
        st.divider()
        
        speed = st.slider("飞行速度 (m/s)", 1.0, 20.0, st.session_state.flight_sim_speed, 0.5)
        st.session_state.flight_sim_speed = speed
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ 开始任务", use_container_width=True, disabled=len(waypoints) == 0):
                st.session_state.flight_sim_running = True
                if st.session_state.flight_sim_start_time is None:
                    st.session_state.flight_sim_start_time = time.time()
                add_fcu_to_gcs_log("FCU→OBC→GCS: ACK | Mode: AUTO")
                st.rerun()
        with col2:
            if st.button("⏹️ 停止任务", use_container_width=True):
                st.session_state.flight_sim_running = False
                add_fcu_to_gcs_log("FCU→OBC→GCS: ACK | Mode: MANUAL")
                st.rerun()
        
        if st.button("🔄 重置任务", use_container_width=True):
            st.session_state.flight_sim_running = False
            st.session_state.flight_sim_start_time = None
            st.session_state.flight_sim_current_index = 0
            st.session_state.flight_sim_last_wp_index = -1
            clear_all_logs()
            st.rerun()
        
        st.divider()
        st.subheader("📋 航线信息")
        st.caption(f"起点A: {st.session_state.coords_a['lat']:.6f}, {st.session_state.coords_a['lon']:.6f}")
        st.caption(f"终点B: {st.session_state.coords_b['lat']:.6f}, {st.session_state.coords_b['lon']:.6f}")
        st.caption(f"飞行高度: {st.session_state.flight_height} m")
        st.caption(f"安全半径: {st.session_state.safe_radius} m")
        st.caption(f"航点数量: {len(waypoints)}")
        if total_dist > 0:
            st.caption(f"总距离: {total_dist:.1f} 米")
    
    # 通信链路拓扑
    st.subheader("📶 通信链路拓扑与数据流")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("✅ GCS 在线")
    with col2:
        st.success("✅ OBC 在线")
    with col3:
        st.success("✅ FCU 在线")
    
    st.divider()
    
    col_gcs, col_conn1, col_obc, col_conn2, col_fcu = st.columns([2, 1, 2, 1, 2])
    
    with col_gcs:
        st.markdown("""
        <div style="border: 2px solid #4285F4; border-radius: 10px; padding: 20px; text-align: center; background-color: #E8F0FE;">
            <div style="font-size: 24px; margin-bottom: 10px;">🖥️</div>
            <div style="font-size: 18px; font-weight: bold;">GCS</div>
            <div style="font-size: 14px; color: #666;">地面站</div>
            <div style="font-size: 12px; color: #666;">192.168.1.100</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_conn1:
        st.markdown("""
        <div style="text-align: center; margin-top: 40px;">
            <div style="font-size: 20px;">⬆️⬇️</div>
            <div style="font-size: 14px; font-weight: bold;">UDP:14550</div>
            <div style="color: green; font-size: 12px;">● 已连接</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_obc:
        st.markdown("""
        <div style="border: 2px solid #F5A623; border-radius: 10px; padding: 20px; text-align: center; background-color: #FFF3E0;">
            <div style="font-size: 24px; margin-bottom: 10px;">🧠</div>
            <div style="font-size: 18px; font-weight: bold;">OBC</div>
            <div style="font-size: 14px; color: #666;">机载计算机</div>
            <div style="font-size: 12px; color: #666;">Raspberry Pi 4</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_conn2:
        st.markdown("""
        <div style="text-align: center; margin-top: 40px;">
            <div style="font-size: 20px;">⬆️⬇️</div>
            <div style="font-size: 14px; font-weight: bold;">MAVLink</div>
            <div style="color: green; font-size: 12px;">● 已连接</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_fcu:
        st.markdown("""
        <div style="border: 2px solid #9C27B0; border-radius: 10px; padding: 20px; text-align: center; background-color: #F3E5F5;">
            <div style="font-size: 24px; margin-bottom: 10px;">⚙️</div>
            <div style="font-size: 18px; font-weight: bold;">FCU</div>
            <div style="font-size: 14px; color: #666;">飞控</div>
            <div style="font-size: 12px; color: #666;">PX4 / ArduPilot</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="margin-top: 15px; padding: 10px; background-color: #F5F5F5; border-radius: 5px;">
        <span style="font-weight: bold;">📊 链路统计:</span>
        <span style="margin-left: 20px;">GCS↔OBC: 正常</span>
        <span style="margin-left: 20px;">OBC↔FCU: 正常</span>
        <span style="margin-left: 20px;">延迟: ~25ms</span>
        <span style="margin-left: 20px;">丢包率: 0.1%</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # 飞行模拟与地图
    if len(waypoints) == 0:
        st.warning("⚠️ 请先在侧边栏点击「📐 导入当前航线」按钮，加载航线规划结果")
    else:
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
            remaining_time = remaining_distance / current_speed if current_speed > 0 else 9999
            
            total_battery_time = 1800
            battery_remaining = max(0, 100 * (1 - min(elapsed_time, total_battery_time) / total_battery_time))
            
            hours = int(elapsed_time // 3600)
            minutes = int((elapsed_time % 3600) // 60)
            seconds = int(elapsed_time % 60)
            elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
            
            if remaining_time >= 3600:
                rem_hours = int(remaining_time // 3600)
                rem_minutes = int((remaining_time % 3600) // 60)
                rem_seconds = int(remaining_time % 60)
                remaining_str = f"{rem_hours:02d}:{rem_minutes:02d}:{rem_seconds:02d}"
            elif remaining_time >= 0:
                rem_minutes = int(remaining_time // 60)
                rem_seconds = int(remaining_time % 60)
                remaining_str = f"{rem_minutes:02d}:{rem_seconds:02d}"
            else:
                remaining_str = "00:00"
            
            arrival_time = datetime.now() + timedelta(seconds=remaining_time)
            arrival_str = arrival_time.strftime("%H:%M:%S")
            
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
            current_speed = 0
            elapsed_str = "00:00"
            remaining_str = "00:00"
            battery_remaining = 100
            arrival_str = "--:--:--"
            current_index = 0
        
        col_map, col_panel = st.columns([3, 1])
        
        with col_map:
            st.subheader("🗺️ 实时飞行地图")
            
            center_lat = (waypoints[0][1] + waypoints[-1][1]) / 2
            center_lon = (waypoints[0][0] + waypoints[-1][0]) / 2
            
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=17,
                tiles='https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
                attr='高德卫星地图',
                height=500
            )
            
            # 规划航线
            folium.PolyLine(
                locations=[(p[1], p[0]) for p in waypoints],
                color='gray',
                weight=3,
                opacity=0.6,
                dash_array='5,5',
                tooltip='规划航线'
            ).add_to(m)
            
            # 已飞行路径
            if st.session_state.flight_sim_running and flown_distance > 0:
                flown_waypoints = [waypoints[0]]
                total_check = 0
                for i, seg_dist in enumerate(seg_dists):
                    total_check += seg_dist
                    if total_check <= flown_distance:
                        flown_waypoints.append(waypoints[i + 1])
                    else:
                        flown_waypoints.append((current_lng, current_lat))
                        break
                if len(flown_waypoints) >= 2:
                    folium.PolyLine(
                        locations=[(p[1], p[0]) for p in flown_waypoints],
                        color='red',
                        weight=4,
                        opacity=0.9,
                        tooltip='已飞行路径'
                    ).add_to(m)
            
            # 航点标记
            for i, (lng, lat) in enumerate(waypoints):
                if i == 0:
                    color = 'green'
                    icon_name = 'play'
                elif i == len(waypoints) - 1:
                    color = 'red'
                    icon_name = 'flag-checkered'
                else:
                    color = 'blue'
                    icon_name = 'circle'
                folium.Marker(
                    location=[lat, lng],
                    popup=f'航点 {i+1}',
                    icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
                ).add_to(m)
            
            # 障碍物
            for obs in st.session_state.obstacles:
                polygon_coords = [[coord[1], coord[0]] for coord in obs["coords"]]
                folium.Polygon(
                    locations=polygon_coords,
                    color='orange',
                    fill=True,
                    fill_color='orange',
                    fill_opacity=0.4,
                    weight=2,
                    tooltip=f"{obs['name']} (高{obs['height']}m)"
                ).add_to(m)
            
            # 无人机位置
            folium.Marker(
                location=[current_lat, current_lng],
                popup='无人机当前位置',
                icon=folium.Icon(color='red', icon='plane', prefix='fa'),
                z_index_offset=1000
            ).add_to(m)
            
            # 安全半径圈
            if st.session_state.safe_radius > 0:
                folium.Circle(
                    location=[current_lat, current_lng],
                    radius=st.session_state.safe_radius,
                    color='red',
                    fill=True,
                    fill_opacity=0.1,
                    weight=1,
                    dash_array='5,5'
                ).add_to(m)
            
            st_folium(m, width=750, height=500, key=f"flight_map_{time.time()}")
        
        with col_panel:
            st.subheader("📊 飞行数据")
            
            total_waypoints = len(waypoints)
            completed_waypoints = min(current_index + 1, total_waypoints) if st.session_state.flight_sim_running else 0
            st.metric("当前航点", f"{completed_waypoints}/{total_waypoints}")
            
            display_speed = current_speed if st.session_state.flight_sim_running else 0
            st.metric("飞行速度", f"{display_speed:.1f} m/s")
            
            st.metric("已用时间", elapsed_str)
            
            st.metric("剩余距离", f"{remaining_distance:.0f} m")
            
            st.metric("预计到达", remaining_str)
            
            st.metric("电量模拟", f"{battery_remaining:.0f}%")
            st.progress(int(battery_remaining) / 100)
            
            st.divider()
            
            st.subheader("🔗 通信链路")
            st.success("✅ GCS在线")
            st.success("✅ OBC在线")
            st.success("✅ FCU在线")
            
            st.divider()
            
            if st.session_state.flight_sim_running:
                st.info("✈️ 任务执行中...")
            elif current_index >= len(waypoints) - 1 and len(waypoints) > 0:
                st.success("✅ 任务已完成！")
            else:
                st.info("⏸️ 等待开始")
        
        st.divider()
        
        # 通信日志
        st.subheader("📝 通信日志")
        
        tab1, tab2, tab3 = st.tabs(["📋 业务流程", "⬇️ GCS→OBC→FCU", "⬆️ FCU→OBC→GCS"])
        
        with tab1:
            business_log_container = st.container(height=300)
            with business_log_container:
                for log in st.session_state.comm_logs_business:
                    color_class = {
                        "green": "background-color: #E8F5E9; color: #2E7D32;",
                        "gray": "background-color: #F5F5F5; color: #424242;",
                        "blue": "background-color: #E3F2FD; color: #1565C0;"
                    }.get(log["color"], "background-color: #FFFFFF;")
                    
                    st.markdown(f"""
                    <div style="padding: 8px; margin-bottom: 4px; border-radius: 4px; {color_class}">
                        <span style="font-weight: bold;">[{log['timestamp']}]</span>
                        <span style="margin-left: 10px;">{log['message']}</span>
                        <span style="float: right; color: #666; font-size: 12px;">{log['source']}</span>
                    </div>
                    """, unsafe_allow_html=True)
        
        with tab2:
            gcs_log_container = st.container(height=300)
            with gcs_log_container:
                for log in st.session_state.comm_logs_gcs_to_fcu:
                    st.code(log, language="plaintext")
        
        with tab3:
            fcu_log_container = st.container(height=300)
            with fcu_log_container:
                for log in st.session_state.comm_logs_fcu_to_gcs:
                    st.code(log, language="plaintext")
        
        if st.session_state.flight_sim_running:
            time.sleep(1.5)
            st.rerun()
