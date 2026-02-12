import streamlit as st
import pandas as pd
import time
from simulation import Simulation
import altair as alt

st.set_page_config(page_title="Perudo Simulation Dashboard", layout="wide")

# Initialize Session State
if "processed_history" not in st.session_state:
    st.session_state.processed_history = None
    st.session_state.final_scores = None
    st.session_state.agents = []
    st.session_state.agent_colors = {} 
    st.session_state.visualization_done = False 

st.title("🎲 Perudo Simulation")

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("Configuration")
    n_tables = st.slider("Number of Tables", 1, 50, 40)
    n_replications = st.slider("Replications per Table", 10, 500, 100)
    
    st.divider()
    
    # Speed Control
    playback_speed = 0.15

    if st.button("Reset Dashboard"):
        st.session_state.processed_history = None
        st.session_state.visualization_done = False
        st.rerun()

@st.dialog("Simulation Status")
def show_sim_dialog(message):
    st.success(message)
    if st.button("Close & Continue"): st.rerun()

# --- PHASE 1: SIMULATION ---
if st.sidebar.button("🔥 Run Simulation"):
    st.info("Simulation is running. Please wait...")
    start_sim = time.perf_counter()
    sim = Simulation(n_tables=n_tables, n_replications=n_replications)
    
    final_scores, winners_vector = sim.start(return_history=True)
    
    st.session_state.sim_time = time.perf_counter() - start_sim
    st.session_state.final_scores = final_scores

    # --- PHASE 2: PROBABILITY CALCULATION ---
    df_wins = pd.Series(winners_vector).str.get_dummies().cumsum()
    game_counts = range(1, len(df_wins) + 1)
    df_probs = df_wins.div(game_counts, axis=0)
    
    df_probs.insert(0, "game", game_counts)
    st.session_state.processed_history = df_probs
    
    agents_list = sorted([c for c in df_probs.columns if c != "game"])
    st.session_state.agents = agents_list
    
    palette = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', 
        '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ]
    st.session_state.agent_colors = {
        name: palette[i % len(palette)] for i, name in enumerate(agents_list)
    }
    
    st.session_state.visualization_done = False
    
    show_sim_dialog(f"Simulation completed in {st.session_state.sim_time:.2f}s")

# --- PHASE 3: VISUALIZATION ---
if st.session_state.processed_history is not None:
    st.write("---")
    
    col1, col2 = st.columns([3, 1.4]) 
    chart_placeholder = col1.empty()
    leaderboard_placeholder = col2.empty()
    podium_placeholder = st.empty() 

    start_btn = st.button("📈 Start Visualization")
    
    full_df = st.session_state.processed_history
    total_games = len(full_df)
    agent_to_color = st.session_state.agent_colors

    if start_btn:
        # 1. Calculate step size
        step = max(1, total_games // 50)
        
        # 2. NEW: Create explicit list of steps
        # We iterate from 1 to total_games.
        progress_steps = list(range(1, total_games + 1, step))
        
        # 3. NEW: Ensure the last frame (total_games) is included
        if progress_steps[-1] != total_games:
            progress_steps.append(total_games)
        
        # Animation loop over the corrected list
        for i in progress_steps:
            current_slice = full_df.iloc[:i]
            last_row = current_slice.iloc[-1]
            
            with chart_placeholder.container():
                st.subheader("Win %")
                chart_data = current_slice.melt('game', var_name='Agent', value_name='prob')
                
                st.vega_lite_chart(chart_data, {
                    'mark': {'type': 'line', 'interpolate': 'monotone'},
                    'encoding': {
                        'x': {
                            'field': 'game', 
                            'type': 'quantitative', 
                            'title': 'Games Played',
                            'scale': {'domain': [1, total_games]} 
                        },
                        'y': {
                            'field': 'prob', 
                            'type': 'quantitative', 
                            'title': 'Win %', 
                            'scale': {'domain': [0, 1]}
                        },
                        'color': {
                            'field': 'Agent', 
                            'type': 'nominal', 
                            'scale': {"domain": list(agent_to_color.keys()), "range": list(agent_to_color.values())},
                            'legend': {'orient': 'bottom'}
                        }
                    },
                    'width': 'container', 'height': 450,
                })

            with leaderboard_placeholder.container():
                st.subheader("Leaderboard")
                lb_rows = [{"Agent": a, "Prob": last_row[a]} for a in st.session_state.agents]
                lb_df = pd.DataFrame(lb_rows).sort_values("Prob", ascending=False)
                
                styled_html = "<table style='width:100%; border-collapse: collapse;'>"
                for _, row in lb_df.iterrows():
                    color = agent_to_color.get(row['Agent'], "#333")
                    styled_html += f"""
                    <tr style='border-bottom: 1px solid #444;'>
                        <td style='padding: 8px;'><span style='background-color:{color}; color:white; padding:2px 8px; border-radius:10px; font-weight:bold;'>{row['Agent']}</span></td>
                        <td style='text-align:right; font-family:monospace; font-size:1.1em;'>{row['Prob']:.1%}</td>
                    </tr>"""
                styled_html += "</table>"
                st.write(styled_html, unsafe_allow_html=True)
            
            # Use variable speed
            time.sleep(playback_speed)
        
        st.session_state.visualization_done = True
        # st.balloons()

    # --- FINAL STATE RENDER (Static) ---
    # When the animation is done (or has finished running), we display the final result statically.
    # This ensures it remains visible after a rerun (e.g., resize).
    if st.session_state.visualization_done:
        # We simply render the last frame statically here if the loop is over
        # (The code above in 'if start_btn' only runs during the animation)
        
        # If the button was NOT just pressed, we need to restore the chart:
        if not start_btn:
            # Restore Chart
            with chart_placeholder.container():
                st.subheader("Win Probability Convergence (Final)")
                chart_data = full_df.melt('game', var_name='Agent', value_name='prob')
                st.vega_lite_chart(chart_data, {
                    'mark': {'type': 'line', 'interpolate': 'monotone'},
                    'encoding': {
                        'x': {'field': 'game', 'type': 'quantitative', 'title': 'Games Played', 'scale': {'domain': [1, total_games]}},
                        'y': {'field': 'prob', 'type': 'quantitative', 'title': 'Win Probability', 'scale': {'domain': [0, 1]}},
                        'color': {'field': 'Agent', 'type': 'nominal', 'scale': {"domain": list(agent_to_color.keys()), "range": list(agent_to_color.values())}, 'legend': {'orient': 'bottom'}}
                    },
                    'width': 'container', 'height': 450,
                })
            
            # Restore Leaderboard
            with leaderboard_placeholder.container():
                st.subheader("Final Probabilities")
                last_row = full_df.iloc[-1]
                lb_rows = [{"Agent": a, "Prob": last_row[a]} for a in st.session_state.agents]
                lb_df = pd.DataFrame(lb_rows).sort_values("Prob", ascending=False)
                styled_html = "<table style='width:100%; border-collapse: collapse;'>"
                for _, row in lb_df.iterrows():
                    color = agent_to_color.get(row['Agent'], "#333")
                    styled_html += f"<tr style='border-bottom: 1px solid #444;'><td style='padding: 8px;'><span style='background-color:{color}; color:white; padding:2px 8px; border-radius:10px; font-weight:bold;'>{row['Agent']}</span></td><td style='text-align:right; font-family:monospace; font-size:1.1em;'>{row['Prob']:.1%}</td></tr>"
                styled_html += "</table>"
                st.write(styled_html, unsafe_allow_html=True)

        # # Podium Reveal (Always visible when visualization_done)
        # with podium_placeholder.container():
        #     st.markdown("---")
        #     sorted_agents = sorted(st.session_state.final_scores.items(), key=lambda x: x[1], reverse=True)
        #     top_3 = [{"name": n, "wins": w, "pct": (w / total_games) * 100, "color": agent_to_color.get(n, "#333")} for n, w in sorted_agents[:3]]

        #     w1 = top_3[0]
        #     st.markdown(f"""<div style="background-color: {w1['color']}; padding: 30px; border-radius: 15px; text-align: center; color: white; margin-bottom: 20px;">
        #         <h2 style="margin:0;">🏆 1st: {w1['name'].upper()}</h2>
        #         <p style="font-size: 1.3em; margin:0;">{w1['wins']} Wins ({w1['pct']:.1f}%)</p>
        #     </div>""", unsafe_allow_html=True)

        #     if len(top_3) > 1:
        #         c2, c3 = st.columns(2)
        #         with c2:
        #             w2 = top_3[1]
        #             st.markdown(f"""<div style="background-color: {w2['color']}; padding: 15px; border-radius: 12px; text-align: center; color: white;">
        #                 <h3 style="margin:0; font-size: 1.1em;">🥈 2nd: {w2['name'].upper()}</h3>
        #                 <p style="font-size: 0.9em; margin:0;">{w2['wins']} Wins ({w2['pct']:.1f}%)</p>
        #             </div>""", unsafe_allow_html=True)
        #         if len(top_3) > 2:
        #             w3 = top_3[2]
        #             with c3:
        #                 st.markdown(f"""<div style="background-color: {w3['color']}; padding: 15px; border-radius: 12px; text-align: center; color: white;">
        #                     <h3 style="margin:0; font-size: 1.1em;">🥉 3rd: {w3['name'].upper()}</h3>
        #                     <p style="font-size: 0.9em; margin:0;">{w3['wins']} Wins ({w3['pct']:.1f}%)</p>
        #                 </div>""", unsafe_allow_html=True)             