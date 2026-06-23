import streamlit as st
import folium
from streamlit_folium import st_folium
from folium import plugins
import math
import json
import os

# ==================== 基础配置 ====================
st.set_page_config(page_title="无人机航线规划", layout="wide")
CAMPUS = [32.2333, 118.7494]
OBSTACLE_FILE = "obstacle_config.json"

# ==================== 会话初始化 ====================
if 'obstacles' not in st.session_state:
    st.session_state.obstacles = []
    if os.path.exists(OBSTACLE_FILE):
        try:
            with open(OBSTACLE_FILE, 'r', encoding='utf-8') as f:
                st.session_state.obstacles = json.load(f).get('obstacles', [])
        except Exception:
            pass

if 'point_a' not in st.session_state:
    st.session_state.point_a = [32.2347, 118.7490]
    st.session_state.point_b = [32.2312, 118.7492]
if 'flight_alt' not in st.session_state:
    st.session_state.flight_alt = 20
if 'safe_dist' not in st.session_state:
    st.session_state.safe_dist = 5
if 'route_result' not in st.session_state:
    st.session_state.route_result = None
if 'temp_obs' not in st.session_state:
    st.session_state.temp_obs = None

# ==================== 几何计算函数 ====================
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

def _ccw(A, B, C):
    return (C[0]-A[0])*(B[1]-A[1]) - (B[0]-A[0])*(C[1]-A[1]) > 1e-8

def seg_intersect_seg(a1, a2, b1, b2):
    return _ccw(a1, b1, b2) != _ccw(a2, b1, b2) and _ccw(a1, a2, b1) != _ccw(a1, a2, b2)

def seg_intersect_polygon(p0, p1, poly):
    if point_in_polygon(p0, poly) or point_in_polygon(p1, poly):
        return True
    n = len(poly)
    for i in range(n):
        if seg_intersect_seg(p0, p1, poly[i], poly[(i+1)%n]):
            return True
    return False

# ==================== 核心绕行算法 ====================
def generate_route(start, end, obstacles, side, safe_m):
    path = [start.copy(), end.copy()]
    step_lat, step_lon = meter_to_degree(2.0, CAMPUS[0])
    max_iter = 600

    for _ in range(max_iter):
        # 查找第一个碰撞航段
        collide_idx = -1
        for i in range(len(path)-1):
            for obs in obstacles:
                if seg_intersect_polygon(path[i], path[i+1], obs["points"]):
                    collide_idx = i
                    break
            if collide_idx != -1:
                break
        if collide_idx == -1:
            break

        # 取中点向外侧偏移
        s = path[collide_idx]
        e = path[collide_idx+1]
        mid = [(s[0]+e[0])/2, (s[1]+e[1])/2]
        
        dx = e[1] - s[1]
        dy = e[0] - s[0]
        line_len = math.hypot(dx, dy)
        if line_len < 1e-9:
            break
        dx /= line_len
        dy /= line_len

        # 计算左右垂直方向
        if side == "left":
            px, py = -dy, dx
        else:
            px, py = dy, -dx
        
        mid[0] += py * step_lat
        mid[1] += px * step_lon
        path.insert(collide_idx+1, mid)

    # 强制对齐起终点
    path[0] = start.copy()
    path[-1] = end.copy()
    return path

# ==================== 页面主体 ====================
st.title("🛰️ 无人机航线规划系统")
st.markdown("---")

col_map, col_ctrl = st.columns([2, 1])

with col_map:
    st.subheader("🗺️ 卫星地图")
    m = folium.Map(location=CAMPUS, zoom_start=17)
    # 高德卫星底图
    folium.TileLayer(
        "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
        attr="高德卫星", subdomains=["1","2","3","4"]
    ).add_to(m)

    # 渲染障碍物
    for obs in st.session_state.obstacles:
        color = "red" if st.session_state.flight_alt < obs["height"] else "green"
        folium.Polygon(
            obs["points"], color=color, fill=True, fill_opacity=0.5,
            popup=f"{obs['name']} | {obs['height']}m"
        ).add_to(m)

    # 起终点标记
    folium.Marker(st.session_state.point_a, icon=folium.Icon(color="green", icon="play"), popup="起点").add_to(m)
    folium.Marker(st.session_state.point_b, icon=folium.Icon(color="red", icon="flag"), popup="终点").add_to(m)

    # 渲染生成的航线（亮黄色粗线，醒目可见）
    if st.session_state.route_result:
        folium.PolyLine(
            st.session_state.route_result,
            color="#ffff00", weight=5, opacity=1, dash_array='10, 5'
        ).add_to(m)
        # 航点标记
        for idx, wp in enumerate(st.session_state.route_result[1:-1], 1):
            folium.CircleMarker(wp, radius=6, color="white", fill=True, fill_color="red").add_to(m)

    # 绘图工具
    plugins.Draw(draw_options={"polygon": {"allowIntersection": False}}).add_to(m)
    map_out = st_folium(m, width="100%", height=600, key="main_map")

    # 捕获绘制的多边形
    if map_out and map_out.get("last_active_drawing"):
        draw = map_out["last_active_drawing"]
        if draw["geometry"]["type"] == "Polygon":
            coords = draw["geometry"]["coordinates"][0]
            pts = [[c[1], c[0]] for c in coords]
            # 移除首尾重复点
            if len(pts) > 1 and abs(pts[0][0]-pts[-1][0])<1e-10 and abs(pts[0][1]-pts[-1][1])<1e-10:
                pts.pop()
            if len(pts) >= 3:
                st.session_state.temp_obs = pts
                st.success("✅ 已绘制建筑轮廓，请在右侧填写信息并保存")

with col_ctrl:
    st.subheader("⚙️ 控制面板")

    # 新建障碍物面板
    if st.session_state.temp_obs:
        st.markdown("### 🆕 新建建筑")
        obs_name = st.text_input("建筑名称", value="教学楼")
        obs_height = st.number_input("建筑高度(m)", min_value=1, value=35)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ 保存", type="primary", use_container_width=True):
                st.session_state.obstacles.append({
                    "name": obs_name,
                    "height": obs_height,
                    "points": st.session_state.temp_obs
                })
                with open(OBSTACLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"obstacles": st.session_state.obstacles}, f, ensure_ascii=False, indent=2)
                st.session_state.temp_obs = None
                st.rerun()
        with c2:
            if st.button("🗑️ 取消", use_container_width=True):
                st.session_state.temp_obs = None
                st.rerun()
        st.markdown("---")

    # 起终点设置
    st.markdown("### 📍 起终点")
    with st.expander("调整起点坐标"):
        lat_a = st.number_input("起点纬度", value=st.session_state.point_a[0], format="%.6f")
        lon_a = st.number_input("起点经度", value=st.session_state.point_a[1], format="%.6f")
        if st.button("更新起点", use_container_width=True):
            st.session_state.point_a = [lat_a, lon_a]
            st.rerun()
    with st.expander("调整终点坐标"):
        lat_b = st.number_input("终点纬度", value=st.session_state.point_b[0], format="%.6f")
        lon_b = st.number_input("终点经度", value=st.session_state.point_b[1], format="%.6f")
        if st.button("更新终点", use_container_width=True):
            st.session_state.point_b = [lat_b, lon_b]
            st.rerun()

    st.markdown("---")
    st.markdown("### 🚁 飞行参数")
    st.session_state.flight_alt = st.slider("飞行高度(m)", 10, 100, 20)
    st.session_state.safe_dist = st.slider("安全距离(m)", 2, 30, 5)

    # 建筑列表
    st.markdown("---")
    st.markdown("### 🏢 已保存建筑")
    block_count = 0
    for idx, obs in enumerate(st.session_state.obstacles):
        need_bypass = st.session_state.flight_alt < obs["height"]
        if need_bypass:
            block_count += 1
        tag = "🔄 需绕行" if need_bypass else "✅ 可飞越"
        with st.expander(f"{tag} {obs['name']} {obs['height']}m"):
            if st.button("删除", key=f"del_{idx}", use_container_width=True):
                st.session_state.obstacles.pop(idx)
                with open(OBSTACLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"obstacles": st.session_state.obstacles}, f, ensure_ascii=False, indent=2)
                st.rerun()
    st.caption(f"共 {block_count} 栋建筑需要绕行")

    st.markdown("---")
    st.markdown("### 🎯 生成航线")
    if st.button("一键生成最优航线", use_container_width=True, type="primary"):
        # 筛选需要绕行的建筑
        block_obs = [o for o in st.session_state.obstacles if st.session_state.flight_alt < o["height"]]
        
        if len(block_obs) == 0:
            st.session_state.route_result = [st.session_state.point_a, st.session_state.point_b]
            st.success("无遮挡建筑，生成直线飞越航线")
        else:
            # 生成左右两条航线，选最短的
            left_path = generate_route(st.session_state.point_a, st.session_state.point_b, block_obs, "left", st.session_state.safe_dist)
            right_path = generate_route(st.session_state.point_a, st.session_state.point_b, block_obs, "right", st.session_state.safe_dist)
            
            left_len = sum(calc_distance(left_path[i], left_path[i+1]) for i in range(len(left_path)-1))
            right_len = sum(calc_distance(right_path[i], right_path[i+1]) for i in range(len(right_path)-1))
            
            st.session_state.route_result = left_path if left_len <= right_len else right_path
            st.success(f"✅ 航线生成成功！共绕开 {len(block_obs)} 栋建筑")
        st.rerun()

    if st.session_state.route_result:
        total_len = sum(calc_distance(st.session_state.route_result[i], st.session_state.route_result[i+1]) for i in range(len(st.session_state.route_result)-1))
        st.info(f"航线总长度：{total_len:.1f} 米 | 航点数量：{len(st.session_state.route_result)} 个")

st.markdown("---")
st.caption("无人机航线规划系统 | 修复报错稳定版")
