from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

def generate_spatial_report(target_brand, total_comp, top_10_brands, suitability, cannibalization):
    """
    Passes our spatial calculations to an LLM to generate a professional C-suite report.
    """
    llm = ChatGroq(model="llama3-8b-8b", temperature=0.2)
    
    template = """
    You are an expert AI Market Planning Director specializing in retail site selection and GIS spatial intelligence.
    Provide a comprehensive, professional Site Suitability Executive Summary based on the following real-time spatial metrics:
    
    - Target Expansion Brand: {target_brand}
    - Total Competitor Stores within 1km Network: {total_comp}
    - Top 10 Existing Brands in Trade Area: {top_10}
    - Calculated Site Suitability Score (out of 100): {suitability}
    - Sister-Store Cannibalization Score (out of 100): {cannibalization}
    
    Structure your report with the following professional headers:
    1. Executive Recommendation (Go / No-Go Decision)
    2. Trade Area Competitive Saturated Analysis
    3. Risk Mitigation Strategy (Focusing on the Cannibalization vs Poaching Dynamic)
    4. Infrastructure & Demographics Inference (Based on the 1km drive network reality)
    
    Keep the tone highly strategic, crisp, and ready for C-suite presentation.
    """
    
    prompt = PromptTemplate(
        input_variables=["target_brand", "total_comp", "top_10", "suitability", "cannibalization"],
        template=template
    )
    
    chain = prompt | llm
    
    response = chain.invoke({
        "target_brand": target_brand,
        "total_comp": total_comp,
        "top_10": str(top_10_brands),
        "suitability": suitability,
        "cannibalization": cannibalization
    })
    
    return response.content
