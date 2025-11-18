import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd
import re
import tempfile

st.set_page_config(page_title="PDF 排序工具", page_icon="📄", layout="wide")

st.title("📄 PDF 排序工具（按 Excel 条码顺序）")
st.write("上传 Excel + PDF ，自动按条码顺序排序。")

uploaded_excel = st.file_uploader("上传 Excel 映射表（必须包含 label_bar_code 和 carton_code 列）", type=["xlsx"])
uploaded_pdf = st.file_uploader("上传原始 PDF 文件", type=["pdf"])

if uploaded_excel and uploaded_pdf:
    
    if st.button("🚀 开始处理"):
        st.info("正在处理，请稍等…")

        # 读取 Excel
        df = pd.read_excel(uploaded_excel)
        mapping = dict(zip(df['label_bar_code'].astype(str), df['carton_code']))

        # 临时保存 PDF 文件
        tmp_pdf = tempfile.NamedTemporaryFile(delete=False).name
        with open(tmp_pdf, "wb") as f:
            f.write(uploaded_pdf.read())

        reader = PdfReader(tmp_pdf)

        # 提取 PDF 每页条码
        page_to_barcode = {}
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            match = re.search(r'\d{18}', text)
            barcode = match.group() if match else ""
            page_to_barcode[idx] = barcode

        # 按 Excel 顺序排序 PDF
        writer = PdfWriter()
        used_pages = set()
        failed = []

        for barcode in mapping.keys():
            found = False
            for page_idx, code in page_to_barcode.items():
                if code == barcode and page_idx not in used_pages:
                    writer.add_page(reader.pages[page_idx])
                    used_pages.add(page_idx)
                    found = True
                    break
            if not found:
                failed.append(barcode)

        # 输出 PDF
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        with open(output_file, "wb") as f:
            writer.write(f)

        st.success("🎉 处理成功！点击下载 👇")
        with open(output_file, "rb") as f:
            st.download_button("📥 下载排序后的 PDF", f, file_name="sorted_output.pdf")

        if failed:
            st.error("以下条码未匹配到 PDF：")
            st.code("\n".join(failed))
