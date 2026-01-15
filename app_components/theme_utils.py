"""
AgriVision Pro V3 - Theme Utilities
====================================
Dark/light mode CSS support.
"""

import streamlit as st


def apply_theme_css():
    """Apply theme CSS for dark/light mode support."""
    st.markdown("""
    <style>
    /* Landing page hero */
    .landing-hero {
        background: linear-gradient(135deg, #1a472a 0%, #2d7a47 50%, #3cb371 100%);
        color: white;
        padding: 3rem 2rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(45, 122, 71, 0.3);
    }
    
    .landing-title {
        font-size: 3rem;
        font-weight: 600;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    .landing-subtitle {
        font-size: 1.2rem;
        opacity: 0.95;
        margin-bottom: 2rem;
    }
    
    /* Tool cards */
    .tool-card {
        background: white;
        border-radius: 15px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        border: 2px solid transparent;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .tool-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(45, 122, 71, 0.2);
        border-color: #2d7a47;
    }
    
    .tool-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    
    .tool-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        margin-bottom: 0.5rem;
    }
    
    .tool-description {
        color: #666;
        line-height: 1.6;
    }
    
    /* Feature grid */
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 2rem 0;
    }
    
    .feature-item {
        background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #9ae6b4;
        transition: all 0.3s ease;
    }
    
    .feature-item:hover {
        transform: translateY(-3px);
        box-shadow: 0 5px 15px rgba(45, 122, 71, 0.2);
    }
    
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
        color: #2d7a47;
    }
    
    /* Step header */
    .step-header {
        padding: 1rem;
        background: linear-gradient(90deg, #f0fff4, #c6f6d5);
        border-left: 5px solid #2d7a47;
        border-radius: 5px;
        margin: 1rem 0;
    }
    
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .tool-card {
            background: #262730;
            border-color: #464852;
        }
        
        .tool-card:hover {
            border-color: #3cb371;
        }
        
        .tool-title {
            color: #fafafa;
        }
        
        .tool-description {
            color: #d0d0d0;
        }
        
        .feature-item {
            background: linear-gradient(135deg, #1a2332 0%, #243447 100%);
            border-color: #2d7a47;
            color: #fafafa;
        }
        
        .step-header {
            background: linear-gradient(90deg, #1e293b, #334155);
            color: #fafafa;
        }
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .landing-title {
            font-size: 2.5rem;
        }
        
        .feature-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """, unsafe_allow_html=True)
