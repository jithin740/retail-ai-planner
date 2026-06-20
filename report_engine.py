import requests
import json

def generate_ai_report_direct(target_brand, total_comp, top_10_brands, suitability, cannibalization, api_key):
    """
    Bypasses framework translation layers by hitting the Groq REST API 
    directly with the correct model string identifier.
    """
    if not api_key:
        return "⚠️ API credentials missing. Please check your Streamlit Secret Environment variables."
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt_payload = f"""
    You are an expert AI Market Planning Director specializing in retail site selection and GIS spatial intelligence.
    Provide a comprehensive, professional Site Suitability Executive Summary based on the following real-time spatial metrics:
    
    - Target Expansion Brand: {target_brand}
    - Total Competitor Stores within 1km Network: {total_comp}
    - Top 10 Existing Brands in Trade Area: {top_10_brands}
    - Calculated Site Suitability Score (out of 100): {suitability}
    - Sister-Store Cannibalization Score (out of 100): {cannibalization}
    
    Structure your report with the following professional headers:
    1. Executive Recommendation (Go / No-Go Decision)
    2. Trade Area Competitive Saturated Analysis
    3. Risk Mitigation Strategy (Focusing on the Cannibalization vs Poaching Dynamic)
    4. Infrastructure & Demographics Inference (Based on the 1km drive network reality)
    
    Keep the tone highly strategic, crisp, and ready for C-suite presentation. Do not include introductory conversational text.
    """
    
    request_body = {
        "model": "llama-3.1-8b-instant",  # Correct standard Groq deployment ID
        "messages": [
            {"role": "system", "content": "You are an elite corporate retail GIS expansion director."},
            {"role": "user", "content": prompt_payload}
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(request_body), timeout=20)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Groq Engine Connection Alert (Code {response.status_code}): {response.text}"
    except Exception as e:
        return f"⚠️ Automated reporting layer interface timeout: {str(e)}"
