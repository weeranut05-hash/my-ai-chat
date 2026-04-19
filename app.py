import streamlit as st
import pandas as pd
import sqlite3
from google import genai
from google.genai import types
import json

# --- CONFIGURATION ---
# ดึง API Key จาก Secrets
gemini_api_key = st.secrets["gemini_api_key"]
gmn_client = genai.Client(api_key=gemini_api_key)

# รายละเอียดฐานข้อมูล
db_name = 'test_database.db'
data_table = 'transactions'
data_dict_text = """
- trx_date: วันที่ทำธุรกรรม
- trx_no: หมายเลขธุรกรรม
- member_code: รหัสสมาชิกของลูกค้า
- branch_code: รหัสสาขา
- branch_region: ภูมิภาคที่สาขาตั้งอยู่
- branch_province: จังหวัดที่สาขาตั้งอยู่
- product_code: รหัสสินค้า
- product_category: หมวดหมู่หลักของสินค้า
- product_group: กลุ่มของสินค้า
- product_type: ประเภทของสินค้า
- order_qty: จำนวนชิ้น/หน่วย ที่ลูกค้าสั่งซื้อ
- unit_price: ราคาขายของสินค้าต่อหน่วย
- cost: ต้นทุนของสินค้าต่อหน่วย
- item_discount: ส่วนลดเฉพาะรายการสินค้านั้นๆ
- customer_discount: ส่วนลดจากสิทธิของลูกค้า
- net_amount: ยอดขายสุทธิของรายการนั้น
- cost_amount: ต้นทุนรวมของรายการนั้น
"""

# --- HELPER FUNCTIONS ---
def query_to_dataframe(sql_query, database_name):
    """รัน SQL และคืนค่าเป็น DataFrame"""
    try:
        connection = sqlite3.connect(database_name)
        result_df = pd.read_sql_query(sql_query, connection)
        connection.close()
        return result_df
    except Exception as e:
        return f"Database Error: {e}"

def generate_gemini_answer(prompt, is_json=False):
    """เรียก Gemini API"""
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json" if is_json else "text/plain" 
        )
        response = gmn_client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

# --- PROMPT TEMPLATES ---
script_prompt = """
### Goal
สร้าง SQLite script ที่ถูกต้องเพื่อตอบคำถามจากข้อมูลที่มี โดยส่งออกเป็น JSON เท่านั้น
### Context
คุณคือ SQLite Master ห้ามตอบเป็นคำพูด ให้ตอบเฉพาะโค้ดที่ใช้งานได้จริง
### Input
- คำถาม: <Question> {question} </Question>
- ชื่อ Table: <Table_Name> {table_name} </Table_Name>
- Schema: <Schema> {data_dict} </Schema>
### Output
ตอบกลับเป็น JSON object รูปแบบเดียวเท่านั้น: {{"script": "SELECT ... FROM ..."}}
(ห้ามมีคำอธิบายประกอบ หรือ Markdown นอกเหนือจาก JSON)
"""

answer_prompt = """
### Goal
สรุปผลลัพธ์จากข้อมูลและตอบคำถามอย่างถูกต้อง
### Context
คุณคือ Data Analyst สรุปผลจาก DataFrame และตอบคำถามผู้ใช้
### Input
- คำถาม: <Question> {question} </Question>
- ข้อมูล: <Raw_Data> {raw_data} </Raw_Data>
### Process
สรุปข้อมูลให้เป็นภาษาไทย ระบุตัวเลขพร้อมหน่วยให้ชัดเจน
### Output
ตอบเป็นข้อความสรุปสั้นๆ ที่เข้าใจง่าย
"""

# --- CORE LOGIC ---
def generate_summary_answer(user_question):
    # 1. สร้าง Prompt สำหรับ SQL
    script_prompt_input = script_prompt.format(
        question=user_question,
        table_name=data_table,
        data_dict=data_dict_text
    )
    # เรียกใช้ฟังก์ชันที่ประกาศไว้ด้านบน
    sql_json_text = generate_gemini_answer(script_prompt_input, is_json=True)
    
    try:
        sql_script = json.loads(sql_json_text)['script']
    except:
        return "ขออภัย ไม่สามารถสร้างคำสั่ง SQL ได้"

    # 2. Query ข้อมูล
    df_result = query_to_dataframe(sql_script, db_name)
    if isinstance(df_result, str):
        return df_result

    # 3. สรุปคำตอบ
    answer_prompt_input = answer_prompt.format(
        question=user_question,
        raw_data=df_result.to_string()
    )
    return generate_gemini_answer(answer_prompt_input, is_json=False)

# --- USER INTERFACE ---
st.set_page_config(page_title="Gemini SQL Chat", page_icon="📊")

# ตรวจสอบและสร้าง Chat History ใน Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title('📊 Gemini Chat with Database')
st.caption("สอบถามข้อมูลยอดขายผ่าน AI Data Analyst")

# แสดงประวัติการสนทนา
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# รับ Input
if prompt := st.chat_input("พิมพ์คำถามที่นี่..."):
    # เก็บและแสดงข้อความ User
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ประมวลผลและแสดงข้อความ Assistant
    with st.chat_message("assistant"):
        with st.spinner('กำลังหาคำตอบ...'):
            response = generate_summary_answer(prompt)
            st.markdown(response)

    # เก็บคำตอบลง Session
    st.session_state.messages.append({"role": "assistant", "content": response})
