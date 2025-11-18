import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd
import re
import tempfile
import os

st.set_page_config(page_title="PDF 排序工具", page_icon="📄", layout="wide")

st.title("📄 PDF 排序工具（按 Excel 条码顺序）")
st.write("选择目的仓类型，上传 Excel + PDF，自动按条码顺序排序。")

# 初始化session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'download_file' not in st.session_state:
    st.session_state.download_file = None
if 'failed_list' not in st.session_state:
    st.session_state.failed_list = []
if 'success_count' not in st.session_state:
    st.session_state.success_count = 0

# 重置函数
def reset_processing():
    st.session_state.processed = False
    st.session_state.download_file = None
    st.session_state.failed_list = []
    st.session_state.success_count = 0

# 侧边栏选择目的仓类型
with st.sidebar:
    st.header("⚙️ 配置")
    warehouse_type = st.selectbox(
        "选择目的仓类型",
        ["FBA", "AWD"],
        help="FBA: 匹配FBA条码 | AWD: 匹配18位数字条码"
    )
    
    if st.button("🔄 重置处理结果", use_container_width=True):
        reset_processing()
        st.rerun()

# 文件上传区域
uploaded_excel = st.file_uploader(
    "上传 Excel 映射表（必须包含 label_bar_code 和 carton_code 列）", 
    type=["xlsx"]
)
uploaded_pdf = st.file_uploader(
    "上传原始 PDF 文件", 
    type=["pdf"]
)

if uploaded_excel and uploaded_pdf and not st.session_state.processed:
    
    if st.button("🚀 开始处理", type="primary"):
        with st.spinner("正在处理，请稍等…"):
            try:
                # 读取 Excel
                df = pd.read_excel(uploaded_excel)
                
                # 检查必要的列是否存在
                if 'label_bar_code' not in df.columns or 'carton_code' not in df.columns:
                    st.error("❌ Excel文件中必须包含 'label_bar_code' 和 'carton_code' 列")
                    st.stop()
                
                mapping = dict(zip(df['label_bar_code'].astype(str), df['carton_code']))

                # 临时保存 PDF 文件
                tmp_pdf = tempfile.NamedTemporaryFile(delete=False).name
                with open(tmp_pdf, "wb") as f:
                    f.write(uploaded_pdf.read())

                reader = PdfReader(tmp_pdf)

                # 根据目的仓类型选择不同的条码匹配方式
                page_to_barcode = {}
                
                if warehouse_type == "FBA":
                    st.info("🔍 使用 FBA 条码匹配方式")
                    # FBA 匹配逻辑
                    for idx, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        
                        # 多种匹配模式尝试
                        patterns = [
                            r'FBA[A-Z0-9]{17}',  # 匹配 FBA + 17位字母数字
                            r'FBA\d{3}[A-Z0-9]{14}',  # 更具体的模式：FBA + 3数字 + 14位字母数字
                            r'[A-Z0-9]{20}',  # 匹配20位字母数字
                            r'\b[A-Z0-9]{15,25}\b'  # 匹配15-25位字母数字（单词边界）
                        ]
                        
                        barcode = ""
                        for pattern in patterns:
                            match = re.search(pattern, text)
                            if match:
                                barcode = match.group()
                                break
                        
                        page_to_barcode[idx] = barcode

                else:  # AWD
                    st.info("🔍 使用 AWD 条码匹配方式")
                    # AWD 匹配逻辑
                    for idx, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        match = re.search(r'\d{18}', text)
                        barcode = match.group() if match else ""
                        page_to_barcode[idx] = barcode

                # 显示条码提取统计
                extracted_count = sum(1 for code in page_to_barcode.values() if code)
                st.write(f"📊 条码提取统计: 总页数 {len(reader.pages)}，成功提取条码 {extracted_count} 页")

                # 按 Excel 顺序排序 PDF
                writer = PdfWriter()
                used_pages = set()
                failed = []

                # 进度条
                progress_bar = st.progress(0)
                total_barcodes = len(mapping.keys())
                
                for i, barcode in enumerate(mapping.keys()):
                    found = False
                    for page_idx, code in page_to_barcode.items():
                        if code == barcode and page_idx not in used_pages:
                            writer.add_page(reader.pages[page_idx])
                            used_pages.add(page_idx)
                            found = True
                            break
                    
                    if not found:
                        failed.append(barcode)
                    
                    # 更新进度
                    progress_bar.progress((i + 1) / total_barcodes)

                # 输出 PDF
                output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                with open(output_file, "wb") as f:
                    writer.write(f)

                # 保存处理结果到session state
                with open(output_file, "rb") as f:
                    st.session_state.download_file = f.read()
                st.session_state.failed_list = failed
                st.session_state.success_count = len(used_pages)
                st.session_state.processed = True
                
                # 清理临时文件
                try:
                    os.unlink(tmp_pdf)
                    os.unlink(output_file)
                except:
                    pass
                
                st.success("🎉 处理完成！")

            except Exception as e:
                st.error(f"❌ 处理过程中出现错误: {str(e)}")

# 显示处理结果和下载
if st.session_state.processed:
    st.divider()
    st.subheader("📋 处理结果")
    
    total_count = st.session_state.success_count + len(st.session_state.failed_list)
    
    # 显示统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总条码数", total_count)
    with col2:
        st.metric("成功匹配", st.session_state.success_count)
    with col3:
        st.metric("未匹配", len(st.session_state.failed_list))
    
    # 只显示失败列表（不显示成功明细）
    if st.session_state.failed_list:
        st.error(f"❌ 以下 {len(st.session_state.failed_list)} 个条码未匹配到 PDF：")
        
        # 分列显示失败条码
        cols = st.columns(3)
        failed_list = st.session_state.failed_list
        items_per_col = (len(failed_list) + 2) // 3
        
        for i, col in enumerate(cols):
            start_idx = i * items_per_col
            end_idx = min((i + 1) * items_per_col, len(failed_list))
            if start_idx < len(failed_list):
                with col:
                    for item in failed_list[start_idx:end_idx]:
                        st.code(item)
    else:
        st.success("✅ 所有条码都成功匹配！")
    
    # 下载按钮
    if st.session_state.download_file:
        st.download_button(
            "📥 下载排序后的 PDF",
            st.session_state.download_file,
            file_name=f"sorted_output_{warehouse_type}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )

# 使用说明
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 操作步骤:
    1. **选择目的仓类型** - FBA 或 AWD
    2. **上传 Excel 文件** - 必须包含 `label_bar_code` 和 `carton_code` 列
    3. **上传 PDF 文件** - 包含需要排序的页面
    4. **点击「开始处理」** - 系统自动匹配条码并排序
    5. **下载结果** - 获取排序后的PDF文件

    ### 条码格式说明:
    - **FBA**: FBA开头 + 字母数字组合 (如: FBA193CJMR8PU000029)
    - **AWD**: 18位纯数字条码

    ### 注意事项:
    - 确保Excel中的条码与PDF中的条码完全一致
    - 处理完成后只显示未匹配的条码列表
    - 点击「重置处理结果」可以重新处理当前文件
    - 重新上传文件会自动重置处理状态
    """)
