import random
import time
import urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================================
st.set_page_config(page_title="FUTEBOL_SERENO", layout="wide")

# ==========================================================
# CONFIGURAÇÕES GERAIS
# ==========================================================
INFO_CREDENCIAIS = dict(st.secrets["gcp_service_account"])
NOME_PLANILHA = "FUTEBOL_SERENO"

ABA_CADASTRO = "CADASTRO_JOGADORES"
ABA_PRESENCA = "LISTA_PRESENCA"
ABA_SORTEIO = "LISTA_SORTEIO"

COLUNAS_CADASTRO = ["NOME", "MENSALISTA", "DIARISTA", "CONVIDADO", "CRIANÇA", "POSICAO"]
COLUNAS_PRESENCA = ["NOME", "PRESENCA"]
COLUNAS_SORTEIO = ["Ordem", "Time A", "Time B", "SORTEIO"]

OPCOES_POSICAO = ["ZAGUEIRO", "MEIO CAMPO", "ATACANTE"]
OPCOES_CATEGORIA = ["MENSALISTA", "DIARISTA", "CONVIDADO", "CRIANÇA"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
FORMATO_SORTEIO = "%Y-%m-%d %H:%M:%S"

# ==========================================================
# ACESSO ADMINISTRADOR
# ==========================================================
ADMIN_USUARIO = "Sereno"
ADMIN_SENHA = "fc"

# ==========================================================
# CONTROLE DE NOVO SORTEIO / LIMPAR SORTEIO
# ==========================================================
TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS = 10 * 60
SENHA_MASTER_SORTEIO = "@"

# ==========================================================
# ESTILO
# ==========================================================
def aplicar_estilo_global():
    st.markdown(
        """
        <style>
        :root {
            --sereno-bg: #050505;
            --sereno-card: rgba(18,18,18,0.92);
            --sereno-card-2: rgba(22,22,22,0.95);
            --sereno-borda: rgba(255,255,255,0.08);
            --sereno-laranja: #ff6a00;
            --sereno-laranja-2: #ff8c1a;
            --sereno-texto: #f5f5f5;
            --sereno-texto-2: #bdbdbd;
            --sereno-danger: #b91c1c;
            --sereno-success: #16a34a;
        }

        html, body, [class*="css"] {
            font-family: "Arial", sans-serif;
        }

        .stApp {
            background:
                linear-gradient(rgba(0,0,0,0.80), rgba(0,0,0,0.88)),
                url("https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1600&q=80");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: var(--sereno-texto);
        }

        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1450px;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(8,8,8,0.96), rgba(12,12,12,0.98));
            border-right: 1px solid rgba(255,255,255,0.06);
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.2rem;
        }

        [data-testid="stHeader"] {
            background: rgba(0,0,0,0);
        }

        .sereno-hero {
            background: linear-gradient(180deg, rgba(15,15,15,0.88), rgba(10,10,10,0.92));
            border: 1px solid rgba(255,255,255,0.05);
            border-top: 4px solid var(--sereno-laranja);
            border-radius: 24px;
            padding: 22px 28px;
            margin-bottom: 18px;
            box-shadow: 0 12px 32px rgba(0,0,0,0.28);
        }

        .sereno-hero h1 {
            margin: 0;
            color: #fff;
            font-size: 3rem;
            font-weight: 900;
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .sereno-hero p {
            margin: 8px 0 0 0;
            color: #d3d3d3;
            font-size: 1.05rem;
        }

        .sereno-card {
            background: linear-gradient(180deg, rgba(20,20,20,0.96), rgba(10,10,10,0.96));
            border: 1px solid rgba(255,255,255,0.06);
            border-top: 4px solid var(--sereno-laranja);
            border-radius: 22px;
            padding: 20px;
            box-shadow: 0 14px 32px rgba(0,0,0,0.26);
            margin-bottom: 16px;
        }

        .sereno-card-header {
            font-size: 1.8rem;
            font-weight: 900;
            color: #fff;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }

        .sereno-card-sub {
            font-size: 0.98rem;
            color: #c4c4c4;
            margin-bottom: 16px;
        }

        .sereno-section-title {
            font-size: 1.45rem;
            font-weight: 900;
            color: #fff;
            text-transform: uppercase;
            margin-bottom: 14px;
            letter-spacing: 1px;
        }

        .sereno-mini-title {
            font-size: 1rem;
            font-weight: 800;
            color: #f3f3f3;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        div[data-testid="stForm"] {
            background: rgba(12,12,12,0.72);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 18px;
            padding: 16px 16px 10px 16px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        .stTextInput input,
        .stTextArea textarea {
            background: #050505 !important;
            color: #ffffff !important;
            border-radius: 14px !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
        }

        .stTextInput label p,
        .stSelectbox label p,
        .stTextArea label p {
            color: #d7d7d7 !important;
            font-weight: 700 !important;
        }

        div[data-baseweb="select"] svg,
        div[data-baseweb="select"] span {
            color: white !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background: rgba(0,0,0,0.25);
            padding: 8px;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.05);
            margin-bottom: 18px;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            color: #d6d6d6;
            height: 48px;
            padding: 0 18px;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, #ff7a12, #ff6a00) !important;
            color: #fff !important;
            box-shadow: 0 8px 18px rgba(255,106,0,0.28);
        }

        .stTabs button p {
            font-size: 1rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.5px;
        }

        .stButton > button,
        .stDownloadButton > button,
        .stLinkButton a {
            border-radius: 14px !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            font-weight: 800 !important;
            min-height: 46px !important;
            color: white !important;
            background: linear-gradient(180deg, #ff7a12, #ff6a00) !important;
            box-shadow: 0 10px 18px rgba(255,106,0,0.18);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        .stLinkButton a:hover {
            filter: brightness(1.06);
            border-color: rgba(255,255,255,0.16) !important;
        }

        .sereno-btn-neutral button {
            background: linear-gradient(180deg, #2e2e2e, #1f1f1f) !important;
            box-shadow: none !important;
        }

        .sereno-btn-danger button {
            background: linear-gradient(180deg, #7f1d1d, #450a0a) !important;
            box-shadow: none !important;
        }

        .sereno-muted {
            color: #b7b7b7;
        }

        .sereno-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 10px;
            font-size: 0.85rem;
            font-weight: 900;
            letter-spacing: 0.4px;
            color: #ff9a3c;
            background: rgba(255,106,0,0.10);
            border: 1px solid rgba(255,106,0,0.35);
            text-transform: uppercase;
        }

        .sereno-player-row {
            background: rgba(7,7,7,0.72);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 10px 14px;
            margin-bottom: 10px;
        }

        .sereno-player-name {
            color: #ffffff;
            font-weight: 900;
            font-size: 1.08rem;
            margin-bottom: 2px;
        }

        .sereno-player-meta {
            color: #c7c7c7;
            font-size: 0.92rem;
            text-transform: uppercase;
        }

        .sereno-presenca-card {
            background: rgba(35, 16, 0, 0.55);
            border: 2px solid rgba(255,106,0,0.72);
            border-radius: 18px;
            padding: 8px 14px 2px 14px;
            margin-bottom: 12px;
        }

        div[data-testid="stCheckbox"] {
            background: rgba(0,0,0,0.18);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 8px 10px;
            margin-bottom: 8px;
        }

        div[data-testid="stCheckbox"] label p {
            color: #fff !important;
            font-size: 1.18rem !important;
            font-weight: 800 !important;
        }

        .sereno-table-wrap {
            overflow-x: auto;
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 18px;
            background: rgba(10,10,10,0.82);
        }

        table.sereno-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 780px;
        }

        table.sereno-table thead th {
            background: #050505;
            color: #d9d9d9;
            text-align: left;
            padding: 14px 16px;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }

        table.sereno-table tbody td {
            padding: 14px 16px;
            color: #f4f4f4;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        table.sereno-table tbody tr:hover {
            background: rgba(255,106,0,0.06);
        }

        .sereno-centralizado {
            text-align: center !important;
        }

        .sereno-empty {
            text-align: center;
            color: #a5a5a5;
            font-size: 1.1rem;
            padding: 60px 20px;
        }

        .sereno-side-logo {
            text-align: center;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            margin-bottom: 14px;
        }

        .sereno-side-logo h2 {
            color: #fff;
            margin: 12px 0 4px 0;
            font-size: 2rem;
            font-weight: 900;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        .sereno-side-logo p {
            color: #ff8f2a;
            margin: 0;
            font-weight: 700;
        }

        .sereno-admin-box {
            background: rgba(43, 22, 0, 0.85);
            border: 1px solid rgba(255,106,0,0.35);
            border-radius: 16px;
            padding: 12px 14px;
            color: white;
        }

        .sereno-admin-box small {
            color: #cfcfcf;
            display: block;
            margin-bottom: 3px;
        }

        .sereno-confirm-box {
            background: rgba(45,20,0,0.82);
            border: 1px solid rgba(255,106,0,0.35);
            border-radius: 18px;
            padding: 16px;
            margin-top: 12px;
        }

        .sereno-confirm-box .titulo {
            color: #fff;
            font-size: 1.05rem;
            font-weight: 800;
            margin-bottom: 10px;
        }

        .sereno-foot {
            text-align: center;
            color: #bfbfbf;
            margin-top: 18px;
            font-size: 0.95rem;
            font-weight: 700;
        }

        div[data-testid="stAlert"] {
            border-radius: 16px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def formatar_opcao_vazia(texto):
    return "Selecione..." if texto == "" else texto

def card_titulo(titulo, subtitulo=""):
    st.markdown(
        f"""
        <div class="sereno-card">
            <div class="sereno-card-header">{titulo}</div>
            {'<div class="sereno-card-sub">' + subtitulo + '</div>' if subtitulo else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

def render_table_html(df, centralizar_colunas=None, badge_colunas=None):
    if df.empty:
        return "<div class='sereno-table-wrap'><div class='sereno-empty'>Sem dados.</div></div>"

    centralizar_colunas = centralizar_colunas or []
    badge_colunas = badge_colunas or []

    colunas_html = ""
    for col in df.columns:
        classe = "sereno-centralizado" if col in centralizar_colunas else ""
        colunas_html += f"<th class='{classe}'>{col}</th>"

    linhas_html = ""
    for _, row in df.iterrows():
        linhas_html += "<tr>"

        is_reserva = False
        if "Ordem" in df.columns:
            try:
                if int(str(row["Ordem"]).strip()) >= 12:
                    is_reserva = True
            except Exception:
                pass

        for col in df.columns:
            valor = row[col]
            valor = "" if pd.isna(valor) else str(valor)
            classe = "sereno-centralizado" if col in centralizar_colunas else ""

            if col in badge_colunas and valor.strip():
                valor = f"<span class='sereno-badge'>{valor}</span>"

            if is_reserva and col in ["Time A", "Time B"] and valor.strip():
                valor = f"<span style='color:#ff6a6a;font-weight:900;'>{valor}</span>"

            linhas_html += f"<td class='{classe}'>{valor}</td>"
        linhas_html += "</tr>"

    return f"""
    <div class="sereno-table-wrap">
        <table class="sereno-table">
            <thead>
                <tr>{colunas_html}</tr>
            </thead>
            <tbody>
                {linhas_html}
            </tbody>
        </table>
    </div>
    """

def exibir_tabela_html(df, centralizar_colunas=None, badge_colunas=None):
    st.markdown(
        render_table_html(df, centralizar_colunas=centralizar_colunas, badge_colunas=badge_colunas),
        unsafe_allow_html=True
    )

# ==========================================================
# UTILITÁRIOS DE RESILIÊNCIA
# ==========================================================
def executar_com_retry(func, *args, **kwargs):
    tentativas = 6
    espera_inicial = 1.5

    for tentativa in range(tentativas):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            erro_str = str(e)
            if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str:
                if tentativa < tentativas - 1:
                    espera = espera_inicial * (2 ** tentativa)
                    time.sleep(espera)
                    continue
            raise

# ==========================================================
# FUNÇÕES DE TEMPO / SORTEIO GLOBAL
# ==========================================================
def agora_br():
    return datetime.now(FUSO_BR)

def formatar_timestamp_sorteio(dt):
    return dt.strftime(FORMATO_SORTEIO)

def parse_timestamp_sorteio(texto):
    texto = str(texto).strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, FORMATO_SORTEIO).replace(tzinfo=FUSO_BR)
    except Exception:
        return None

# ==========================================================
# WHATSAPP
# ==========================================================
def gerar_texto_whatsapp_sorteio(df_sorteio):
    if df_sorteio.empty:
        return "Ainda não há sorteio realizado!"

    df = df_sorteio.copy()

    for col in ["Ordem", "Time A", "Time B", "SORTEIO"]:
        if col not in df.columns:
            df[col] = ""

    df["Ordem"] = df["Ordem"].astype(str).str.strip()
    df["Time A"] = df["Time A"].astype(str).str.strip()
    df["Time B"] = df["Time B"].astype(str).str.strip()
    df["SORTEIO"] = df["SORTEIO"].astype(str).str.strip()

    df_linhas = df[df["Ordem"] != ""].copy()

    lista_a = [nome for nome in df_linhas["Time A"].tolist() if str(nome).strip()]
    lista_b = [nome for nome in df_linhas["Time B"].tolist() if str(nome).strip()]

    timestamp = ""
    for val in df["SORTEIO"].tolist():
        if str(val).strip():
            timestamp = str(val).strip()
            break

    linhas = []
    linhas.append("🏆 *Resumo do Sorteio - Sereno F.C.*")

    if timestamp:
        linhas.append(f"📅 {timestamp}")

    linhas.append("")
    linhas.append("🔵 *Time A*")
    if lista_a:
        for i, nome in enumerate(lista_a, start=1):
            linhas.append(f"{i}. {nome}")
    else:
        linhas.append("Sem jogadores")

    linhas.append("")
    linhas.append("🔴 *Time B*")
    if lista_b:
        for i, nome in enumerate(lista_b, start=1):
            linhas.append(f"{i}. {nome}")
    else:
        linhas.append("Sem jogadores")

    return "\n".join(linhas)

def gerar_link_whatsapp_sorteio(df_sorteio):
    texto = gerar_texto_whatsapp_sorteio(df_sorteio)
    texto_codificado = urllib.parse.quote(texto)
    return f"https://wa.me/?text={texto_codificado}"

# ==========================================================
# CONEXÃO
# ==========================================================
@st.cache_resource
def conectar_gsheet():
    creds = Credentials.from_service_account_info(
        INFO_CREDENCIAIS,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    planilha = executar_com_retry(client.open, NOME_PLANILHA)

    worksheets = executar_com_retry(planilha.worksheets)
    mapa_abas = {ws.title: ws for ws in worksheets}

    return planilha, mapa_abas

def obter_worksheet(mapa_abas, nome_aba):
    if nome_aba not in mapa_abas:
        raise ValueError(f"A aba '{nome_aba}' não foi encontrada na planilha.")
    return mapa_abas[nome_aba]

def limpar_cache_planilha():
    ler_valores_aba_cacheado.clear()

# ==========================================================
# CACHE DE LEITURA PARA REDUZIR 429
# ==========================================================
@st.cache_data(ttl=15)
def ler_valores_aba_cacheado(nome_aba):
    _, mapa_abas = conectar_gsheet()
    ws = obter_worksheet(mapa_abas, nome_aba)
    return executar_com_retry(ws.get_all_values)

def ler_valores_aba_tempo_real(mapa_abas, nome_aba):
    ws = obter_worksheet(mapa_abas, nome_aba)
    return executar_com_retry(ws.get_all_values)

# ==========================================================
# FUNÇÕES DE LEITURA/ESCRITA
# ==========================================================
def ler_aba_com_cabecalho(mapa_abas, nome_aba, colunas_esperadas):
    valores = ler_valores_aba_cacheado(nome_aba)

    if not valores:
        return pd.DataFrame(columns=colunas_esperadas)

    cabecalho = valores[0]
    linhas = valores[1:]

    if not cabecalho:
        return pd.DataFrame(columns=colunas_esperadas)

    if not linhas:
        return pd.DataFrame(columns=colunas_esperadas)

    linhas_ajustadas = []
    total_colunas = len(cabecalho)

    for linha in linhas:
        linha = list(linha)
        if len(linha) < total_colunas:
            linha.extend([""] * (total_colunas - len(linha)))
        elif len(linha) > total_colunas:
            linha = linha[:total_colunas]
        linhas_ajustadas.append(linha)

    df = pd.DataFrame(linhas_ajustadas, columns=cabecalho)

    for col in colunas_esperadas:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_esperadas].fillna("")
    return df

def escrever_dataframe_na_aba(mapa_abas, nome_aba, df, colunas_esperadas):
    ws = obter_worksheet(mapa_abas, nome_aba)

    df = df.copy()

    for col in colunas_esperadas:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_esperadas].fillna("")
    valores = [colunas_esperadas] + df.astype(str).values.tolist()

    executar_com_retry(ws.clear)
    executar_com_retry(ws.update, "A1", valores)
    limpar_cache_planilha()

def inicializar_abas_se_necessario(mapa_abas):
    configuracoes = [
        (ABA_CADASTRO, COLUNAS_CADASTRO),
        (ABA_PRESENCA, COLUNAS_PRESENCA),
        (ABA_SORTEIO, COLUNAS_SORTEIO),
    ]

    for nome_aba, colunas in configuracoes:
        ws = obter_worksheet(mapa_abas, nome_aba)
        valores = executar_com_retry(ws.get_all_values)

        if not valores:
            executar_com_retry(ws.update, "A1", [colunas])
        else:
            cabecalho_atual = valores[0]
            if cabecalho_atual != colunas:
                dados_existentes = valores[1:] if len(valores) > 1 else []
                novos_valores = [colunas]

                for linha in dados_existentes:
                    linha = list(linha)
                    if len(linha) < len(colunas):
                        linha.extend([""] * (len(colunas) - len(linha)))
                    elif len(linha) > len(colunas):
                        linha = linha[:len(colunas)]
                    novos_valores.append(linha)

                executar_com_retry(ws.clear)
                executar_com_retry(ws.update, "A1", novos_valores)

    limpar_cache_planilha()

# ==========================================================
# FUNÇÕES DE NEGÓCIO
# ==========================================================
def normalizar_nome(nome):
    return str(nome).strip()

def normalizar_posicao(posicao):
    p = str(posicao).strip().upper()
    return p if p in OPCOES_POSICAO else ""

def normalizar_categoria(categoria):
    c = str(categoria).strip().upper()
    return c if c in OPCOES_CATEGORIA else ""

def chave_checkbox_presenca(nome):
    return f"presenca_checkbox::{normalizar_nome(nome)}"

def montar_linha_cadastro(nome, categoria, posicao):
    return {
        "NOME": nome,
        "MENSALISTA": "SIM" if categoria == "MENSALISTA" else "NÃO",
        "DIARISTA": "SIM" if categoria == "DIARISTA" else "NÃO",
        "CONVIDADO": "SIM" if categoria == "CONVIDADO" else "NÃO",
        "CRIANÇA": "SIM" if categoria == "CRIANÇA" else "NÃO",
        "POSICAO": posicao,
    }

def descobrir_categoria_jogador(linha):
    if str(linha.get("MENSALISTA", "")).upper() == "SIM":
        return "MENSALISTA"
    if str(linha.get("DIARISTA", "")).upper() == "SIM":
        return "DIARISTA"
    if str(linha.get("CONVIDADO", "")).upper() == "SIM":
        return "CONVIDADO"
    if str(linha.get("CRIANÇA", "")).upper() == "SIM":
        return "CRIANÇA"
    return ""

def obter_ultimo_timestamp_sorteio(mapa_abas):
    valores = ler_valores_aba_tempo_real(mapa_abas, ABA_SORTEIO)
    if not valores:
        return None

    cabecalho = valores[0]
    if "SORTEIO" not in cabecalho:
        return None

    idx = cabecalho.index("SORTEIO")
    ultimo_dt = None

    for linha in valores[1:]:
        valor = linha[idx] if idx < len(linha) else ""
        dt = parse_timestamp_sorteio(valor)
        if dt and (ultimo_dt is None or dt > ultimo_dt):
            ultimo_dt = dt

    return ultimo_dt

def obter_segundos_restantes_bloqueio(mapa_abas):
    ultimo_dt = obter_ultimo_timestamp_sorteio(mapa_abas)
    if ultimo_dt is None:
        return 0

    diferenca = (agora_br() - ultimo_dt).total_seconds()
    restante = TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS - int(diferenca)
    return max(0, restante)

def montar_df_presenca_sincronizado(mapa_abas):
    df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
    df_presenca = ler_aba_com_cabecalho(mapa_abas, ABA_PRESENCA, COLUNAS_PRESENCA)

    nomes_cadastro = [
        normalizar_nome(x) for x in df_cadastro["NOME"].tolist()
        if normalizar_nome(x)
    ]

    presenca_atual = {}
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome:
            presenca_atual[nome] = str(row["PRESENCA"]).upper().strip() or "NÃO"

    novas_linhas = []
    for nome in nomes_cadastro:
        novas_linhas.append({
            "NOME": nome,
            "PRESENCA": presenca_atual.get(nome, "NÃO")
        })

    novo_df_presenca = pd.DataFrame(novas_linhas, columns=COLUNAS_PRESENCA)
    df_presenca_atual_normalizado = pd.DataFrame(columns=COLUNAS_PRESENCA)

    if not df_presenca.empty:
        df_presenca_atual_normalizado = df_presenca.copy()
        for col in COLUNAS_PRESENCA:
            if col not in df_presenca_atual_normalizado.columns:
                df_presenca_atual_normalizado[col] = ""
        df_presenca_atual_normalizado = df_presenca_atual_normalizado[COLUNAS_PRESENCA].fillna("")

    return novo_df_presenca, df_presenca_atual_normalizado

def sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False):
    novo_df_presenca, df_presenca_atual = montar_df_presenca_sincronizado(mapa_abas)

    atual = df_presenca_atual.astype(str).values.tolist() if not df_presenca_atual.empty else []
    novo = novo_df_presenca.astype(str).values.tolist() if not novo_df_presenca.empty else []

    if forcar_gravacao or atual != novo:
        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)

    return novo_df_presenca

def inicializar_estado_checkboxes_presenca(df_presenca):
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        if not nome:
            continue
        chave = chave_checkbox_presenca(nome)
        if chave not in st.session_state:
            st.session_state[chave] = str(row["PRESENCA"]).upper().strip() == "SIM"

def forcar_estado_checkboxes_presenca(df_presenca, marcado):
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome:
            st.session_state[chave_checkbox_presenca(nome)] = marcado

def aplicar_df_presenca_ao_estado(df_presenca):
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome:
            st.session_state[chave_checkbox_presenca(nome)] = str(row["PRESENCA"]).upper().strip() == "SIM"

def construir_df_presenca_a_partir_dos_checkboxes(df_presenca_base):
    linhas = []
    for _, row in df_presenca_base.iterrows():
        nome = normalizar_nome(row["NOME"])
        if not nome:
            continue

        marcado = bool(st.session_state.get(chave_checkbox_presenca(nome), False))
        linhas.append({
            "NOME": nome,
            "PRESENCA": "SIM" if marcado else "NÃO"
        })

    return pd.DataFrame(linhas, columns=COLUNAS_PRESENCA)

def formatar_tempo_restante(segundos):
    minutos = int(segundos // 60)
    segundos_restantes = int(segundos % 60)
    return f"{minutos:02d}:{segundos_restantes:02d}"

def distribuir_grupo_para_listas(itens_embaralhados, time_1, time_2):
    proximo_time = 1 if len(time_1) <= len(time_2) else 2

    for item in itens_embaralhados:
        if proximo_time == 1:
            time_1.append(item)
            proximo_time = 2
        else:
            time_2.append(item)
            proximo_time = 1

def sortear_times(df_cadastro, df_presenca):
    cadastro_map = {}
    for _, row in df_cadastro.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome:
            cadastro_map[nome] = {
                "categoria": descobrir_categoria_jogador(row.to_dict()),
                "posicao": normalizar_posicao(row.to_dict().get("POSICAO", ""))
            }

    presentes = []
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        presenca = str(row["PRESENCA"]).upper().strip()
        if nome and presenca == "SIM" and nome in cadastro_map:
            presentes.append({
                "nome": nome,
                "categoria": cadastro_map[nome]["categoria"],
                "posicao": cadastro_map[nome]["posicao"]
            })

    grupos = {
        "MENSALISTA": [],
        "DIARISTA": [],
        "CONVIDADO": [],
        "CRIANÇA": []
    }

    for jogador in presentes:
        categoria = jogador["categoria"]
        if categoria in grupos:
            grupos[categoria].append(jogador)

    for categoria in grupos:
        random.shuffle(grupos[categoria])

    ordem_categorias = ["MENSALISTA", "DIARISTA", "CONVIDADO", "CRIANÇA"]

    time_1_objs = []
    time_2_objs = []

    for categoria in ordem_categorias:
        jogadores_grupo = grupos[categoria]
        if jogadores_grupo:
            distribuir_grupo_para_listas(jogadores_grupo, time_1_objs, time_2_objs)

    for i, obj in enumerate(time_1_objs):
        obj["status"] = 1 if i < 11 else 2
    for i, obj in enumerate(time_2_objs):
        obj["status"] = 1 if i < 11 else 2

    def chave_ordenacao(jogador):
        val_status = jogador.get("status", 2)
        ordem_cat = {"MENSALISTA": 1, "DIARISTA": 2, "CONVIDADO": 3, "CRIANÇA": 4}
        ordem_pos = {"ZAGUEIRO": 1, "MEIO CAMPO": 2, "ATACANTE": 3}

        val_cat = ordem_cat.get(jogador["categoria"], 99)
        val_pos = ordem_pos.get(jogador["posicao"], 99)

        return (val_status, val_cat, val_pos)

    time_1_objs.sort(key=chave_ordenacao)
    time_2_objs.sort(key=chave_ordenacao)

    time_1 = [obj["nome"] for obj in time_1_objs if str(obj["nome"]).strip()]
    time_2 = [obj["nome"] for obj in time_2_objs if str(obj["nome"]).strip()]

    max_len = max(len(time_1), len(time_2))
    linhas_sorteio = []

    for i in range(max_len):
        linhas_sorteio.append({
            "Ordem": str(i + 1),
            "Time A": time_1[i] if i < len(time_1) else "",
            "Time B": time_2[i] if i < len(time_2) else "",
        })

    return pd.DataFrame(linhas_sorteio, columns=["Ordem", "Time A", "Time B"])

def anexar_timestamp_sorteio(df_sorteio, timestamp_str):
    df_sorteio = df_sorteio.copy()

    if df_sorteio.empty:
        return pd.DataFrame(
            [{"Ordem": "", "Time A": "", "Time B": "", "SORTEIO": timestamp_str}],
            columns=COLUNAS_SORTEIO
        )

    df_sorteio["SORTEIO"] = ""
    df_sorteio.at[0, "SORTEIO"] = timestamp_str
    return df_sorteio[COLUNAS_SORTEIO]

def realizar_limpeza_sorteio(mapa_abas, msg_sucesso="Sorteio limpo com sucesso."):
    ultimo_dt = obter_ultimo_timestamp_sorteio(mapa_abas)
    timestamp_str = formatar_timestamp_sorteio(ultimo_dt) if ultimo_dt else ""

    if timestamp_str:
        df_vazio = pd.DataFrame(
            [{"Ordem": "", "Time A": "", "Time B": "", "SORTEIO": timestamp_str}],
            columns=COLUNAS_SORTEIO
        )
    else:
        df_vazio = pd.DataFrame(columns=COLUNAS_SORTEIO)

    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_vazio, COLUNAS_SORTEIO)

    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""

    st.success(msg_sucesso)
    st.rerun()

def realizar_sorteio(mapa_abas):
    df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
    df_presenca = ler_aba_com_cabecalho(mapa_abas, ABA_PRESENCA, COLUNAS_PRESENCA)

    df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
    df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()

    df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)
    df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

    presentes_sim = df_presenca[
        df_presenca["PRESENCA"].astype(str).str.upper().str.strip() == "SIM"
    ]

    if df_cadastro.empty:
        st.error("Não há jogadores cadastrados.")
        return

    if df_presenca.empty:
        st.error("A lista de presença está vazia.")
        return

    if presentes_sim.empty:
        realizar_limpeza_sorteio(mapa_abas, msg_sucesso="Sorteio limpo, pois nenhum jogador foi marcado como presente.")
        return

    df_sorteio = sortear_times(df_cadastro, df_presenca)
    timestamp_atual = formatar_timestamp_sorteio(agora_br())
    df_sorteio = anexar_timestamp_sorteio(df_sorteio, timestamp_atual)
    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_sorteio, COLUNAS_SORTEIO)

    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""
    st.session_state.confirmar_sorteio_pendente = False

    st.success("Sorteio realizado com sucesso.")
    st.rerun()

# ==========================================================
# FUNÇÕES DE UI CADASTRO
# ==========================================================
def preparar_edicao_jogador(df_cadastro, nome_jogador):
    alvo = df_cadastro[df_cadastro["NOME"] == nome_jogador]
    if alvo.empty:
        st.error("Jogador não encontrado para edição.")
        return

    linha = alvo.iloc[0].to_dict()
    categoria = descobrir_categoria_jogador(linha)
    posicao = normalizar_posicao(linha.get("POSICAO", ""))

    st.session_state.modo_cadastro = "editar"
    st.session_state.jogador_editando_original = nome_jogador
    st.session_state.form_nome_jogador = nome_jogador
    st.session_state.form_categoria_jogador = categoria
    st.session_state.form_posicao_jogador = posicao

def resetar_form_cadastro():
    st.session_state.modo_cadastro = "novo"
    st.session_state.jogador_editando_original = ""
    st.session_state.form_nome_jogador = ""
    st.session_state.form_categoria_jogador = ""
    st.session_state.form_posicao_jogador = ""

def categoria_e_posicao_do_jogador(row):
    return descobrir_categoria_jogador(row.to_dict()), normalizar_posicao(row.get("POSICAO", ""))

# ==========================================================
# ESTADO INICIAL
# ==========================================================
if "abas_inicializadas" not in st.session_state:
    st.session_state.abas_inicializadas = False

if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

if "admin_erro_login" not in st.session_state:
    st.session_state.admin_erro_login = ""

if "exigir_senha_master_acao" not in st.session_state:
    st.session_state.exigir_senha_master_acao = False

if "erro_senha_master_acao" not in st.session_state:
    st.session_state.erro_senha_master_acao = ""

if "tipo_acao_pendente" not in st.session_state:
    st.session_state.tipo_acao_pendente = ""

if "pendente_excluir_jogador" not in st.session_state:
    st.session_state.pendente_excluir_jogador = ""

if "forcar_atualizacao_presenca" not in st.session_state:
    st.session_state.forcar_atualizacao_presenca = False

if "confirmar_sorteio_pendente" not in st.session_state:
    st.session_state.confirmar_sorteio_pendente = False

if "modo_cadastro" not in st.session_state:
    st.session_state.modo_cadastro = "novo"

if "jogador_editando_original" not in st.session_state:
    st.session_state.jogador_editando_original = ""

if "form_nome_jogador" not in st.session_state:
    st.session_state.form_nome_jogador = ""

if "form_categoria_jogador" not in st.session_state:
    st.session_state.form_categoria_jogador = ""

if "form_posicao_jogador" not in st.session_state:
    st.session_state.form_posicao_jogador = ""

# ==========================================================
# ESTILO
# ==========================================================
aplicar_estilo_global()

# ==========================================================
# SIDEBAR
# ==========================================================
with st.sidebar:
    logo_path = Path("SERENO FC.png")
    st.markdown('<div class="sereno-side-logo">', unsafe_allow_html=True)
    if logo_path.exists():
        st.image(str(logo_path), width=120)
    st.markdown("<h2>SERENO FC</h2>", unsafe_allow_html=True)
    st.markdown("<p>Desde 1966</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Acesso Admin")

    if not st.session_state.admin_autenticado:
        with st.form("form_login_admin", clear_on_submit=True):
            usuario_admin = st.text_input("Usuário", placeholder="Usuário...")
            senha_admin = st.text_input("Senha", type="password", placeholder="Senha...")
            entrar_admin = st.form_submit_button("ENTRAR", use_container_width=True)

        if entrar_admin:
            if usuario_admin == ADMIN_USUARIO and senha_admin == ADMIN_SENHA:
                st.session_state.admin_autenticado = True
                st.session_state.admin_erro_login = ""
                st.session_state.forcar_atualizacao_presenca = True
                st.rerun()
            else:
                st.session_state.admin_erro_login = "Usuário ou senha inválidos."

        if st.session_state.admin_erro_login:
            st.error(st.session_state.admin_erro_login)
    else:
        st.markdown(
            """
            <div class="sereno-admin-box">
                <small>Autenticado como</small>
                <div style="font-size:1.25rem;font-weight:900;">ADMIN</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.write("")
        st.markdown('<div class="sereno-btn-danger">', unsafe_allow_html=True)
        if st.button("SAIR", use_container_width=True):
            st.session_state.admin_autenticado = False
            st.session_state.admin_erro_login = ""
            resetar_form_cadastro()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# TOPO
# ==========================================================
st.markdown(
    """
    <div class="sereno-hero">
        <h1>Sereno F.C.</h1>
        <p>Sistema de cadastro, presença e sorteio de times</p>
    </div>
    """,
    unsafe_allow_html=True
)

# ==========================================================
# APP
# ==========================================================
try:
    planilha, mapa_abas = conectar_gsheet()

    if not st.session_state.abas_inicializadas:
        inicializar_abas_se_necessario(mapa_abas)
        st.session_state.abas_inicializadas = True

    abas = st.tabs([
        "CADASTRO",
        "JOGADORES",
        "PRESENÇA",
        "SORTEIO"
    ])

    # ======================================================
    # ABA 1 - CADASTRO
    # ======================================================
    with abas[0]:
        st.markdown(
            """
            <div class="sereno-card">
                <div class="sereno-card-header">Cadastro</div>
                <div class="sereno-card-sub">Gerenciar os jogadores do Sereno FC</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
        df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
        df_cadastro["POSICAO"] = df_cadastro["POSICAO"].astype(str).str.strip()
        df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

        if st.session_state.admin_autenticado:
            col_esq, col_dir = st.columns([1.05, 1.55], gap="large")

            with col_esq:
                titulo_form = "Novo Jogador" if st.session_state.modo_cadastro == "novo" else "Editar Jogador"
                subtitulo_form = (
                    "Cadastre um novo jogador no elenco."
                    if st.session_state.modo_cadastro == "novo"
                    else f"Editando: {st.session_state.jogador_editando_original}"
                )

                st.markdown(
                    f"""
                    <div class="sereno-card">
                        <div class="sereno-section-title">{titulo_form}</div>
                        <div class="sereno-card-sub">{subtitulo_form}</div>
                    """,
                    unsafe_allow_html=True
                )

                with st.form("form_cadastro_unificado", clear_on_submit=False):
                    nome_padrao = st.session_state.form_nome_jogador
                    categoria_padrao = st.session_state.form_categoria_jogador
                    posicao_padrao = st.session_state.form_posicao_jogador

                    nome_jogador = st.text_input(
                        "Nome completo",
                        value=nome_padrao,
                        placeholder="Ex: Neymar Jr"
                    )

                    idx_categoria = 0
                    if categoria_padrao in OPCOES_CATEGORIA:
                        idx_categoria = OPCOES_CATEGORIA.index(categoria_padrao) + 1

                    categoria = st.selectbox(
                        "Categoria",
                        [""] + OPCOES_CATEGORIA,
                        index=idx_categoria,
                        format_func=formatar_opcao_vazia
                    )

                    idx_posicao = 0
                    if posicao_padrao in OPCOES_POSICAO:
                        idx_posicao = OPCOES_POSICAO.index(posicao_padrao) + 1

                    posicao = st.selectbox(
                        "Posição",
                        [""] + OPCOES_POSICAO,
                        index=idx_posicao,
                        format_func=formatar_opcao_vazia
                    )

                    c_form1, c_form2 = st.columns(2)
                    with c_form1:
                        acao_label = "CADASTRAR" if st.session_state.modo_cadastro == "novo" else "ATUALIZAR"
                        enviar_cadastro = st.form_submit_button(acao_label, use_container_width=True)
                    with c_form2:
                        cancelar_edicao = st.form_submit_button("CANCELAR", use_container_width=True)

                if cancelar_edicao:
                    resetar_form_cadastro()
                    st.rerun()

                if enviar_cadastro:
                    nome_jogador = normalizar_nome(nome_jogador)
                    posicao = normalizar_posicao(posicao)
                    categoria = normalizar_categoria(categoria)

                    if not nome_jogador:
                        st.error("Informe o nome do jogador.")
                    elif not categoria:
                        st.error("Selecione a categoria.")
                    elif not posicao:
                        st.error("Selecione a posição.")
                    else:
                        nomes_existentes_upper = [x.upper() for x in df_cadastro["NOME"].tolist()]

                        if st.session_state.modo_cadastro == "novo":
                            if nome_jogador.upper() in nomes_existentes_upper:
                                st.error("Esse jogador já está cadastrado.")
                            else:
                                nova_linha = montar_linha_cadastro(nome_jogador, categoria, posicao)
                                df_cadastro = pd.concat([df_cadastro, pd.DataFrame([nova_linha])], ignore_index=True)

                                escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                                sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                                resetar_form_cadastro()

                                st.success("Jogador cadastrado com sucesso.")
                                st.rerun()
                        else:
                            nome_original = st.session_state.jogador_editando_original

                            conflito = (
                                nome_jogador.upper() in nomes_existentes_upper and
                                nome_jogador.upper() != nome_original.upper()
                            )

                            if conflito:
                                st.error("Já existe outro jogador com esse nome.")
                            else:
                                idx = df_cadastro.index[df_cadastro["NOME"] == nome_original]
                                if len(idx) == 0:
                                    st.error("Jogador não encontrado para atualização.")
                                else:
                                    idx = idx[0]
                                    linha_atualizada = montar_linha_cadastro(nome_jogador, categoria, posicao)
                                    for col in COLUNAS_CADASTRO:
                                        df_cadastro.at[idx, col] = linha_atualizada[col]

                                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                                    sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                                    resetar_form_cadastro()

                                    st.success("Jogador atualizado com sucesso.")
                                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

            with col_dir:
                st.markdown(
                    """
                    <div class="sereno-card">
                        <div class="sereno-section-title">Jogadores Cadastrados</div>
                    """,
                    unsafe_allow_html=True
                )

                if df_cadastro.empty:
                    st.info("Nenhum jogador cadastrado ainda.")
                else:
                    for i, row in df_cadastro.iterrows():
                        nome = normalizar_nome(row["NOME"])
                        categoria, posicao = categoria_e_posicao_do_jogador(row)

                        linha1, linha2, linha3 = st.columns([6.5, 0.8, 0.8], gap="small")

                        with linha1:
                            st.markdown(
                                f"""
                                <div class="sereno-player-row">
                                    <div class="sereno-player-name">{nome}</div>
                                    <div class="sereno-player-meta">
                                        <span class="sereno-badge">{categoria}</span>
                                        &nbsp;&nbsp; {posicao}
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        with linha2:
                            if st.button("✏️", key=f"editar_jogador_{i}", help=f"Editar {nome}", use_container_width=True):
                                preparar_edicao_jogador(df_cadastro, nome)
                                st.rerun()

                        with linha3:
                            if st.button("🗑️", key=f"excluir_jogador_{i}", help=f"Excluir {nome}", use_container_width=True):
                                st.session_state.pendente_excluir_jogador = nome
                                st.rerun()

                if st.session_state.pendente_excluir_jogador:
                    st.markdown(
                        f"""
                        <div class="sereno-confirm-box">
                            <div class="titulo">Deseja realmente excluir o jogador '{st.session_state.pendente_excluir_jogador}'?</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("CONFIRMAR EXCLUSÃO", use_container_width=True):
                            jogador_alvo = st.session_state.pendente_excluir_jogador
                            df_cadastro = df_cadastro[df_cadastro["NOME"] != jogador_alvo].reset_index(drop=True)
                            escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                            sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)

                            if st.session_state.jogador_editando_original == jogador_alvo:
                                resetar_form_cadastro()

                            st.session_state.pendente_excluir_jogador = ""
                            st.success("Jogador excluído com sucesso.")
                            st.rerun()

                    with c2:
                        st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                        if st.button("CANCELAR", use_container_width=True):
                            st.session_state.pendente_excluir_jogador = ""
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Área de edição restrita ao administrador.")

    # ======================================================
    # ABA 2 - JOGADORES CADASTRADOS
    # ======================================================
    with abas[1]:
        st.markdown(
            """
            <div class="sereno-card">
                <div class="sereno-card-header">Jogadores</div>
                <div class="sereno-card-sub">Lista completa do elenco do Sereno FC</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
        df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
        df_cadastro["POSICAO"] = df_cadastro["POSICAO"].astype(str).str.strip()
        df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

        termo_busca = st.text_input("Buscar jogador", placeholder="Buscar jogador...")

        if df_cadastro.empty:
            st.info("Nenhum jogador cadastrado ainda.")
        else:
            df_exibir = df_cadastro.copy()
            df_exibir["CATEGORIA"] = df_exibir.apply(
                lambda row: descobrir_categoria_jogador(row.to_dict()), axis=1
            )

            if termo_busca.strip():
                filtro = termo_busca.strip().upper()
                df_exibir = df_exibir[
                    df_exibir["NOME"].astype(str).str.upper().str.contains(filtro, na=False) |
                    df_exibir["CATEGORIA"].astype(str).str.upper().str.contains(filtro, na=False) |
                    df_exibir["POSICAO"].astype(str).str.upper().str.contains(filtro, na=False)
                ].reset_index(drop=True)

            if df_exibir.empty:
                st.warning("Nenhum jogador encontrado para a busca informada.")
            else:
                exibir_tabela_html(
                    df_exibir[["NOME", "CATEGORIA", "POSICAO"]],
                    badge_colunas=["CATEGORIA"]
                )

    # ======================================================
    # ABA 3 - PRESENÇA
    # ======================================================
    with abas[2]:
        df_presenca = pd.DataFrame(columns=COLUNAS_PRESENCA)

        if st.session_state.get("forcar_atualizacao_presenca", False):
            limpar_cache_planilha()
            df_fresco = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
            aplicar_df_presenca_ao_estado(df_fresco)
            st.session_state.forcar_atualizacao_presenca = False

        df_presenca = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
        df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()
        df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

        inicializar_estado_checkboxes_presenca(df_presenca)

        total = len(df_presenca)
        confirmados = 0
        for _, row in df_presenca.iterrows():
            nome = normalizar_nome(row["NOME"])
            if st.session_state.get(chave_checkbox_presenca(nome), False):
                confirmados += 1

        st.markdown(
            f"""
            <div class="sereno-card">
                <div class="sereno-card-header">Lista de Presença</div>
                <div class="sereno-card-sub">Confirme os jogadores que vão participar da partida. <span style="color:#ff8c1a;font-weight:900;">{confirmados}/{total} confirmados</span></div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.session_state.admin_autenticado:
            colb1, colb2, colb3, colb4 = st.columns([1, 1, 1, 1.2])

            with colb1:
                st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                if st.button("ATUALIZAR", use_container_width=True):
                    limpar_cache_planilha()
                    df_fresco = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                    aplicar_df_presenca_ao_estado(df_fresco)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with colb2:
                st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                if st.button("MARCAR TODOS", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "SIM"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, True)
                    st.success("Todos os jogadores foram marcados como presentes.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with colb3:
                st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                if st.button("ZERAR", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "NÃO"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, False)
                    st.success("Presenças zeradas com sucesso.")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with colb4:
                if st.button("SALVAR", use_container_width=True):
                    novo_df_presenca = construir_df_presenca_a_partir_dos_checkboxes(df_presenca)
                    escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)
                    aplicar_df_presenca_ao_estado(novo_df_presenca)
                    st.success("Lista de presença salva com sucesso.")
                    st.rerun()

            if df_presenca.empty:
                st.info("Nenhum jogador disponível na lista de presença. Cadastre jogadores na aba CADASTRO.")
            else:
                st.markdown("<div class='sereno-presenca-card'>", unsafe_allow_html=True)
                for _, row in df_presenca.iterrows():
                    nome = normalizar_nome(row["NOME"])
                    st.checkbox(f"**{nome}**", key=chave_checkbox_presenca(nome))
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Alterações de presença restritas ao administrador.")

    # ======================================================
    # ABA 4 - SORTEIO
    # ======================================================
    with abas[3]:
        df_sorteio_leitura = ler_aba_com_cabecalho(mapa_abas, ABA_SORTEIO, COLUNAS_SORTEIO)
        df_sorteio_leitura["Ordem"] = df_sorteio_leitura["Ordem"].astype(str).str.strip()
        df_sorteio_valido = df_sorteio_leitura[df_sorteio_leitura["Ordem"] != ""].reset_index(drop=True)
        tem_jogadores_sorteados = not df_sorteio_valido.empty

        st.markdown(
            """
            <div class="sereno-card">
                <div class="sereno-card-header">Sorteio de Times</div>
                <div class="sereno-card-sub">Gerencie o sorteio e gere o resumo final.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.session_state.admin_autenticado:
            col1, col2, col3 = st.columns([1, 1, 1.2])

            with col1:
                st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                if st.button("ATUALIZAR DADOS", use_container_width=True):
                    limpar_cache_planilha()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                if st.button("LIMPAR SORTEIO", use_container_width=True):
                    restante = obter_segundos_restantes_bloqueio(mapa_abas)
                    if restante <= 0 or not tem_jogadores_sorteados:
                        realizar_limpeza_sorteio(mapa_abas)
                    else:
                        st.session_state.exigir_senha_master_acao = True
                        st.session_state.erro_senha_master_acao = ""
                        st.session_state.tipo_acao_pendente = "limpar"
                st.markdown("</div>", unsafe_allow_html=True)

            with col3:
                if st.button("SORTEAR TIMES", use_container_width=True):
                    st.session_state.confirmar_sorteio_pendente = True
                    st.rerun()

            if st.session_state.confirmar_sorteio_pendente:
                st.markdown(
                    """
                    <div class="sereno-confirm-box">
                        <div class="titulo">Tem certeza que deseja realizar o sorteio? Outro sorteio sem senha só poderá ser feito após 10 minutos.</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                c1, c2 = st.columns(2)

                with c1:
                    if st.button("CONFIRMAR SORTEIO", use_container_width=True):
                        st.session_state.confirmar_sorteio_pendente = False
                        restante = obter_segundos_restantes_bloqueio(mapa_abas)

                        if restante <= 0 or not tem_jogadores_sorteados:
                            realizar_sorteio(mapa_abas)
                        else:
                            st.session_state.exigir_senha_master_acao = True
                            st.session_state.erro_senha_master_acao = ""
                            st.session_state.tipo_acao_pendente = "sortear"
                            st.rerun()

                with c2:
                    st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                    if st.button("CANCELAR", use_container_width=True):
                        st.session_state.confirmar_sorteio_pendente = False
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            if st.session_state.exigir_senha_master_acao:
                restante = obter_segundos_restantes_bloqueio(mapa_abas)
                acao_txt = "novo sorteio" if st.session_state.tipo_acao_pendente == "sortear" else "limpar sorteio"

                st.warning(
                    f"Essa ação só pode ser feita sem senha após 10 minutos. "
                    f"Tempo restante: {formatar_tempo_restante(restante)}. "
                    f"Digite a senha master para autorizar {acao_txt} agora."
                )

                with st.container():
                    senha_master_digitada = st.text_input(
                        "Senha master",
                        type="password",
                        key="senha_master_acao_widget"
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("AUTORIZAR", use_container_width=True):
                            if senha_master_digitada == SENHA_MASTER_SORTEIO:
                                st.session_state.exigir_senha_master_acao = False
                                st.session_state.erro_senha_master_acao = ""

                                if st.session_state.tipo_acao_pendente == "sortear":
                                    realizar_sorteio(mapa_abas)
                                elif st.session_state.tipo_acao_pendente == "limpar":
                                    realizar_limpeza_sorteio(mapa_abas)
                            else:
                                st.session_state.erro_senha_master_acao = "Senha master inválida."

                    with c2:
                        st.markdown('<div class="sereno-btn-neutral">', unsafe_allow_html=True)
                        if st.button("CANCELAR AUTORIZAÇÃO", use_container_width=True):
                            st.session_state.exigir_senha_master_acao = False
                            st.session_state.erro_senha_master_acao = ""
                            st.session_state.tipo_acao_pendente = ""
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

                    if st.session_state.erro_senha_master_acao:
                        st.error(st.session_state.erro_senha_master_acao)
        else:
            st.warning("Sortear e limpar sorteio são ações restritas ao administrador.")

        if not tem_jogadores_sorteados:
            st.markdown(
                """
                <div class="sereno-table-wrap">
                    <div class="sereno-empty">
                        Nenhum sorteio ativo.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            exibir_tabela_html(
                df_sorteio_valido[["Ordem", "Time A", "Time B"]],
                centralizar_colunas=["Ordem", "Time A", "Time B"]
            )

            link_whatsapp = gerar_link_whatsapp_sorteio(df_sorteio_leitura)
            st.link_button("RESUMO PARA WHATSAPP", link_whatsapp, use_container_width=True)

        st.markdown(
            "<div class='sereno-foot'>App criado por: Teori@ / Sereno FC</div>",
            unsafe_allow_html=True
        )

    # ======================================================
    # LOGO NO FINAL DA PÁGINA
    # ======================================================
    col_logo_esq, col_logo_centro, col_logo_dir = st.columns([1, 1.3, 1])
    with col_logo_centro:
        logo_path = Path("SERENO FC.png")
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)

except SpreadsheetNotFound:
    st.error("Planilha 'FUTEBOL_SERENO' não encontrada ou não compartilhada com a service account.")
except Exception as e:
    st.error("Erro ao executar a aplicação.")
    st.exception(e)
