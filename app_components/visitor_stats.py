"""
AgriVision Pro V3 - Visitor Stats Component
============================================
Simple visitor counter using session state.
"""

import streamlit as st
from datetime import datetime


class VisitorStatsComponent:
    """Simple visitor counter component."""
    
    def __init__(self):
        """Initialize visitor stats."""
        if 'visitor_count' not in st.session_state:
            st.session_state.visitor_count = 0
        if 'visitor_counted' not in st.session_state:
            st.session_state.visitor_counted = False
    
    def count_visitor(self):
        """Count this visit if not already counted."""
        if not st.session_state.visitor_counted:
            st.session_state.visitor_count += 1
            st.session_state.visitor_counted = True
    
    def render_sidebar(self):
        """Render visitor stats in sidebar."""
        self.count_visitor()
        
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"👥 **Visitors this session:** {st.session_state.visitor_count}")
    
    def render_footer(self):
        """Render visitor stats in footer."""
        self.count_visitor()
        
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.caption(f"👥 Session visitors: {st.session_state.visitor_count}")
        with col2:
            st.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        with col3:
            st.caption("🌾 AgriVision Pro V3")
