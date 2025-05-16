"""
ワンクリック記事生成アプリケーション
キーワード・想定読者・画像スタイルを入力して、大規模な記事と画像を自動生成
"""
import os
import json
import time
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple

import streamlit as st
from alive_progress import alive_bar

from utils.api_client import APIClient
from utils.outline_generator import OutlineGenerator
from utils.article_generator import ArticleGenerator
from utils.image_generator import ImageGenerator
from utils.file_manager import FileManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize session state variables
def init_session_state():
    """初期セッション状態を設定"""
    if 'api_client' not in st.session_state:
        st.session_state.api_client = None
    if 'openai_api_key' not in st.session_state:
        st.session_state.openai_api_key = ""
    if 'file_manager' not in st.session_state:
        st.session_state.file_manager = FileManager()
    if 'session_dir' not in st.session_state:
        st.session_state.session_dir = None
    if 'outline' not in st.session_state:
        st.session_state.outline = None
    if 'article_sections' not in st.session_state:
        st.session_state.article_sections = []
    if 'image_paths' not in st.session_state:
        st.session_state.image_paths = []
    if 'combined_markdown' not in st.session_state:
        st.session_state.combined_markdown = None
    if 'zip_path' not in st.session_state:
        st.session_state.zip_path = None
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False
    if 'current_step' not in st.session_state:
        st.session_state.current_step = None
    if 'step_progress' not in st.session_state:
        st.session_state.step_progress = 0.0
    if 'step_message' not in st.session_state:
        st.session_state.step_message = ""
    if 'log_messages' not in st.session_state:
        st.session_state.log_messages = []
    # リアルタイム表示用の変数
    if 'current_generating_section' not in st.session_state:
        st.session_state.current_generating_section = None
    if 'current_section_content' not in st.session_state:
        st.session_state.current_section_content = ""
    if 'generated_sections' not in st.session_state:
        st.session_state.generated_sections = {}
    if 'generated_images' not in st.session_state:
        st.session_state.generated_images = {}

def add_log(message: str):
    """ログメッセージを追加"""
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.log_messages.append(f"[{timestamp}] {message}")
    # 最大100件までログを保持
    if len(st.session_state.log_messages) > 100:
        st.session_state.log_messages = st.session_state.log_messages[-100:]

def update_progress(progress: float, message: str):
    """進捗状況を更新"""
    st.session_state.step_progress = progress
    st.session_state.step_message = message
    add_log(message)

def update_generating_section(section_index: int, heading: str, content: str = None):
    """
    現在生成中のセクション情報を更新
    
    Args:
        section_index: セクションのインデックス
        heading: セクションの見出し
        content: 生成されたコンテンツ（あれば）
    """
    st.session_state.current_generating_section = (section_index, heading)
    if content:
        st.session_state.current_section_content = content
        # 完成したセクションを保存
        st.session_state.generated_sections[section_index] = (heading, content)
        add_log(f"セクション {section_index + 1}: {heading} の生成完了")

def update_generating_image(section_index: int, heading: str, image_path: str = None):
    """
    生成された画像情報を更新
    
    Args:
        section_index: セクションのインデックス
        heading: セクションの見出し
        image_path: 生成された画像のパス（あれば）
    """
    if image_path and os.path.exists(image_path):
        st.session_state.generated_images[section_index] = (heading, image_path)
        add_log(f"セクション {section_index + 1}: {heading} の画像生成完了")

async def generate_content(keyword: str, target_audience: str, image_style: str, num_main_headings: int = 30, num_sub_headings: int = 2):
    """
    コンテンツ生成のメインプロセス
    
    Args:
        keyword: 記事のキーワード/トピック
        target_audience: 想定読者
        image_style: 画像スタイル (natural/vivid)
    """
    try:
        # セッションディレクトリを作成
        if not st.session_state.session_dir:
            st.session_state.session_dir = st.session_state.file_manager.create_session_dir()
            add_log(f"セッションディレクトリを作成: {st.session_state.session_dir}")
        
        # APIクライアントを初期化
        if not st.session_state.api_client:
            openai_api_key = st.session_state.openai_api_key
            
            if not openai_api_key:
                st.error("OpenAI APIキーが入力されていません。APIキーを入力してください。")
                add_log("エラー: APIキーが入力されていません")
                st.session_state.is_generating = False
                return
                
            st.session_state.api_client = APIClient(
                openai_api_key=openai_api_key
            )
            add_log("APIクライアントを初期化しました")
        
        # ステップ①: アウトライン生成
        st.session_state.current_step = "outline"
        update_progress(0.1, "アウトライン生成を開始")
        
        outline_generator = OutlineGenerator(st.session_state.api_client)
        st.session_state.outline = await outline_generator.generate_outline(
            keyword=keyword,
            target_audience=target_audience,
            image_style=image_style,
            num_main_headings=num_main_headings,
            num_sub_headings=num_sub_headings
        )
        
        # アウトラインをファイルに保存
        outline_path = os.path.join(st.session_state.session_dir, "outline.json")
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.outline, f, ensure_ascii=False, indent=2)
            
        update_progress(0.2, "アウトライン生成完了")
        
        # ステップ②: 並行記事生成
        st.session_state.current_step = "article"
        update_progress(0.2, "記事生成を開始")
        
        article_generator = ArticleGenerator(st.session_state.api_client, max_concurrent=5)
        sections = await article_generator.generate_all_sections(
            outline=st.session_state.outline,
            keyword=keyword,
            target_audience=target_audience,
            progress_callback=lambda prog, msg: update_progress(0.2 + prog * 0.4, msg)
        )
        
        # 生成されたセクションを保存
        st.session_state.article_sections = sections
        article_dir = os.path.join(st.session_state.session_dir, "articles")
        article_files = await article_generator.save_sections_to_files(sections, article_dir)
        
        # 記事をマークダウンとして結合
        combined_content = article_generator.combine_sections(sections)
        combined_path = os.path.join(st.session_state.session_dir, "article_combined.md")
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write(combined_content)
            
        st.session_state.combined_markdown = combined_content
        update_progress(0.6, "記事生成完了")
        
        # ステップ③: 並行画像生成
        st.session_state.current_step = "image"
        update_progress(0.6, "画像生成を開始")
        
        # 見出しリストを作成
        headings = [section['heading'] for section in st.session_state.outline['outline']]
        
        image_generator = ImageGenerator(st.session_state.api_client, max_concurrent=10)
        image_dir = os.path.join(st.session_state.session_dir, "images")
        
        # 各セクションに対して画像を生成
        image_results = await image_generator.generate_all_images(
            sections=sections,
            headings=headings,
            image_style=image_style,
            output_dir=image_dir,
            progress_callback=lambda prog, msg: update_progress(0.6 + prog * 0.3, msg)
        )
        
        # 画像パスを保存
        st.session_state.image_paths = image_results
        
        # ステップ④: 画像を記事に挿入
        st.session_state.current_step = "combine"
        update_progress(0.9, "記事と画像を結合")
        
        # 相対パスで画像を参照するように結合
        markdown_with_images = image_generator.insert_images_into_markdown(
            combined_markdown=st.session_state.combined_markdown,
            image_paths=image_results,
            base_path="images/"
        )
        
        # 結合したマークダウンを保存
        combined_path = os.path.join(st.session_state.session_dir, "article_with_images.md")
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write(markdown_with_images)
            
        st.session_state.combined_markdown = markdown_with_images
        
        # ステップ⑤: ZIPアーカイブを作成
        st.session_state.current_step = "package"
        update_progress(0.95, "ダウンロードパッケージを作成")
        
        # 記事ファイルと画像ファイルのパスリスト
        article_files = [os.path.join(article_dir, f) for f in os.listdir(article_dir) if f.endswith('.md')]
        image_files = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if f.endswith(('.png', '.jpg'))]
        
        # ZIPを作成
        zip_path = st.session_state.file_manager.create_zip_archive(
            session_dir=st.session_state.session_dir,
            article_files=article_files,
            image_files=image_files,
            combined_markdown_path=combined_path
        )
        
        st.session_state.zip_path = zip_path
        
        # 古いセッションをクリーンアップ
        st.session_state.file_manager.clean_old_sessions(hours=24)
        
        # 現在のセッションの自動クリーンアップをスケジュール
        await st.session_state.file_manager.schedule_cleanup(st.session_state.session_dir, hours=24)
        
        update_progress(1.0, "生成完了！ダウンロードが利用可能です")
        
    except Exception as e:
        logger.error(f"コンテンツ生成中にエラーが発生: {e}")
        add_log(f"エラー: {str(e)}")
        st.error(f"エラーが発生しました: {str(e)}")
    finally:
        st.session_state.is_generating = False

def run_async(coroutine):
    """
    非同期コルーチンを実行するヘルパー関数
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)

def main():
    """メインアプリケーション"""
    st.set_page_config(
        page_title="ワンクリック記事生成",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # セッション状態を初期化
    init_session_state()
    
    # ヘッダー
    st.title("📝 ワンクリック記事生成")
    st.markdown(
        """
        キーワード・想定読者・画像スタイルを入力するだけで、
        30万字以上の記事と30枚の画像を自動生成します。
        """
    )
    
    # APIキー入力
    with st.expander("APIキー設定", expanded=True):
        st.markdown(
            """
            記事生成と画像生成のためにOpenAI APIキーが必要です。
            - OpenAIのAPIキー（GPT-4o）：記事生成に使用
            - OpenAIのAPIキー（DALL-E 3）：画像生成に使用
            
            APIキーはセッション内でのみ保持され、サーバーに保存されません。
            """
        )
        
        # APIキー入力欄
        openai_key = st.text_input(
            "OpenAI API キー", 
            type="password",
            value=st.session_state.openai_api_key,
            placeholder="sk-...", 
            help="OpenAI APIのキー。OpenAIのウェブサイトから取得できます。GPT-4oとDALL-E 3の両方に使用されます。"
        )
        st.session_state.openai_api_key = openai_key
    
    # 入力フォーム
    with st.form("input_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            keyword = st.text_input("キーワード/トピック", help="生成する記事のメインキーワードまたはトピック")
            target_audience = st.text_input("想定読者", help="記事のターゲットとなる読者層")
        
        with col2:
            image_style = st.selectbox(
                "画像スタイル",
                options=["natural", "vivid"],
                format_func=lambda x: "自然な表現 (Natural)" if x == "natural" else "鮮やかな表現 (Vivid)",
                help="生成する画像のスタイル"
            )
            
        # テスト設定（見出し数の設定）
        st.markdown("### テスト設定（オプション）")
        st.markdown("記事の規模を調整するためのオプション設定です。テスト時に小さな値を指定すると処理時間を短縮できます。")
        
        test_col1, test_col2 = st.columns(2)
        
        with test_col1:
            num_main_headings = st.number_input(
                "大見出し数",
                min_value=1,
                max_value=50,
                value=30,
                step=1,
                help="生成する大見出しの数（デフォルト: 30）。テスト時は小さな値（5-10）を推奨"
            )
        
        with test_col2:
            num_sub_headings = st.number_input(
                "各大見出しの小見出し数",
                min_value=1,
                max_value=5,
                value=2,
                step=1,
                help="各大見出しに対する小見出しの数（デフォルト: 2）"
            )
        
        submit_button = st.form_submit_button("生成開始")
        
        if submit_button:
            if not keyword or not target_audience:
                st.error("キーワードと想定読者は必須入力項目です")
            elif not st.session_state.openai_api_key:
                st.error("OpenAI APIキーを入力してください")
            elif st.session_state.is_generating:
                st.warning("既に生成処理が実行中です")
            else:
                st.session_state.is_generating = True
                # 非同期で生成処理を開始
                st.info("生成処理を開始します。このプロセスには時間がかかります。")
                run_async(generate_content(
                    keyword=keyword, 
                    target_audience=target_audience, 
                    image_style=image_style,
                    num_main_headings=int(num_main_headings),
                    num_sub_headings=int(num_sub_headings)
                ))
    
    # タブを作成
    tab1, tab2, tab3, tab4 = st.tabs(["進捗状況", "アウトライン", "プレビュー", "ログ"])
    
    # タブ1: 進捗状況
    with tab1:
        st.subheader("生成の進捗状況")
        
        # 進捗バー
        if st.session_state.is_generating or st.session_state.step_progress > 0:
            st.progress(st.session_state.step_progress)
            st.write(st.session_state.step_message)
            
            # 現在のステップを表示
            steps = ["outline", "article", "image", "combine", "package"]
            current_step_idx = steps.index(st.session_state.current_step) if st.session_state.current_step in steps else -1
            
            cols = st.columns(len(steps))
            for i, (col, step) in enumerate(zip(cols, ["アウトライン", "記事", "画像", "結合", "パッケージ"])):
                if i < current_step_idx:
                    col.success(step)
                elif i == current_step_idx:
                    col.info(step)
                else:
                    col.write(step)
        
        # 生成完了後、ダウンロードボタンを表示
        if st.session_state.zip_path and os.path.exists(st.session_state.zip_path):
            with open(st.session_state.zip_path, "rb") as file:
                st.download_button(
                    label="記事パッケージをダウンロード",
                    data=file,
                    file_name=os.path.basename(st.session_state.zip_path),
                    mime="application/zip",
                    help="記事と画像を含むZIPファイルをダウンロード"
                )
    
    # タブ2: アウトライン
    with tab2:
        st.subheader("記事アウトライン")
        
        if st.session_state.outline:
            # アウトラインを表示
            for i, section in enumerate(st.session_state.outline['outline']):
                heading = section['heading']
                subheadings = section['subheadings']
                
                st.markdown(f"### {i+1}. {heading}")
                for j, subheading in enumerate(subheadings):
                    st.markdown(f"- {subheading}")
        else:
            st.info("アウトラインはまだ生成されていません。")
    
    # タブ3: プレビュー
    with tab3:
        st.subheader("記事プレビュー")
        
        if st.session_state.combined_markdown:
            st.markdown(st.session_state.combined_markdown)
        else:
            st.info("プレビューはまだ利用できません。")
    
    # タブ4: ログ
    with tab4:
        st.subheader("処理ログ")
        
        # ログメッセージを表示
        if st.session_state.log_messages:
            for message in st.session_state.log_messages:
                st.text(message)
        else:
            st.info("ログはまだありません。")
    
    # サイドバー
    with st.sidebar:
        st.subheader("アプリについて")
        st.markdown(
            """
            **ワンクリック記事生成**は、AIの力を活用して大規模な記事と画像を自動生成するツールです。
            
            **機能:**
            - 30の大見出しと60の小見出しを含むアウトライン生成
            - 各章10,000文字以上、計30万字超の記事生成
            - 各章に対応した30枚の画像生成
            - Markdownプレビューと一括ダウンロード
            
            **処理時間の目安:**
            - アウトライン生成: 1〜2分
            - 記事生成: 30〜60分
            - 画像生成: 5〜10分
            
            **注意:**
            生成したファイルは24時間後に自動削除されます。
            必要なファイルは必ずダウンロードしてください。
            """
        )
        
        st.markdown("---")
        
        # シンプルな使用方法
        st.subheader("使用方法")
        st.markdown(
            """
            1. キーワード・想定読者・画像スタイルを入力
            2. 「生成開始」ボタンをクリック
            3. 進捗状況を確認
            4. 生成完了後、記事パッケージをダウンロード
            """
        )

if __name__ == "__main__":
    main()
