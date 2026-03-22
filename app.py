
import calendar
import random
import time
import urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
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
ABA_TORNEIO_DADOS = "TORNEIO_DADOS"
ABA_TORNEIO_SORTEIO = "TORNEIO_SORTEIO"

COLUNAS_CADASTRO = [
    "NOME", "DIRETORIA", "MENSALISTA", "DIARISTA", "CONVIDADO_1", "CONVIDADO_2", "POSICAO"
]
COLUNAS_PRESENCA = ["NOME", "PRESENCA"]
COLUNAS_SORTEIO = ["Ordem", "Time A", "Time B", "SORTEIO"]
COLUNAS_TORNEIO_DADOS = ["CHAVE", "VALOR"]
COLUNAS_TORNEIO_SORTEIO = ["Ordem", "Time A", "Time B", "SORTEIO"]

OPCOES_POSICAO = ["ZAGUEIRO", "MEIO CAMPO", "ATACANTE"]
OPCOES_CATEGORIA = ["DIRETORIA", "MENSALISTA", "DIARISTA", "CONVIDADO_1", "CONVIDADO_2"]

MAPA_CORES_CATEGORIA = {
    "DIRETORIA": "#7c3aed",
    "MENSALISTA": "#2563eb",
    "DIARISTA": "#059669",
    "CONVIDADO_1": "#ea580c",
    "CONVIDADO_2": "#dc2626",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
FORMATO_SORTEIO = "%Y-%m-%d %H:%M:%S"

# ==========================================================
# ACESSO ADMINISTRADOR / SENHAS
# ==========================================================
ADMIN_USUARIO = "Sereno"
ADMIN_SENHA = "fc"
SENHA_MASTER_SORTEIO = "@"
SENHA_TORNEIO = "123"

# ==========================================================
# BLOQUEIOS
# ==========================================================
TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS = 10 * 60
BLOQUEIO_TORNEIO_MESES = 3

CHAVE_TORNEIO_CAPITAO_A = "CAPITAO_TIME_A"
CHAVE_TORNEIO_CAPITAO_B = "CAPITAO_TIME_B"
CHAVE_TORNEIO_DATA_ULTIMO_SORTEIO = "DATA_ULTIMO_SORTEIO_TORNEIO"

# ==========================================================
# ESTILO
# ==========================================================
def aplicar_estilo_global():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 3rem;
            padding-bottom: 2rem;
        }

        .sereno-topo {
            background: linear-gradient(135deg, #fff8f2 0%, #ffffff 50%, #fff5eb 100%);
            border: 1px solid #f0dfd0;
            border-radius: 22px;
            padding: 18px 22px;
            margin-bottom: 16px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.05);
            text-align: center;
        }

        .sereno-titulo {
            font-size: 3.0rem !important;
            font-weight: 900 !important;
            color: #111827;
            margin: 0;
            line-height: 1.3;
        }

        .sereno-subtitulo {
            font-size: 1rem;
            color: #6b7280;
            margin-top: 8px;
            margin-bottom: 0;
        }

        .sereno-tabela-wrapper {
            overflow-x: auto;
            width: 100%;
            border: 1px solid #ececec;
            border-radius: 16px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.04);
            background: #fff;
        }

        table.sereno-table {
            width: 100%;
            min-width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            table-layout: auto;
        }

        table.sereno-table thead th {
            background: #111827;
            color: #ffffff;
            text-align: center;
            padding: 12px 14px;
            font-weight: 700;
            border-bottom: 1px solid #111827;
            white-space: nowrap;
        }

        table.sereno-table tbody td {
            padding: 11px 14px;
            border-bottom: 1px solid #efefef;
            white-space: normal;
            word-break: break-word;
        }

        table.sereno-table tbody tr:nth-child(odd) { background: #fafafa; }
        table.sereno-table tbody tr:nth-child(even) { background: #ffffff; }
        table.sereno-table tbody tr:hover { background: #fff4e8; }

        .sereno-centralizado { text-align: center !important; }

        .sereno-card-presenca,
        .sereno-card-jogadores,
        .sereno-card-torneio {
            background: linear-gradient(180deg, #fffaf5 0%, #ffffff 100%);
            border-radius: 18px;
            padding: 16px 18px 12px 18px;
            box-shadow: 0 8px 18px rgba(0, 0, 0, 0.06);
            margin-bottom: 14px;
            border: 1px solid #ececec;
        }

        .sereno-card-presenca {
            border: 2px solid #f59e0b;
            box-shadow: 0 8px 18px rgba(245, 158, 11, 0.10);
        }

        .sereno-jogador-linha {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 10px 12px;
            border: 1px solid #efefef;
            border-radius: 14px;
            margin-bottom: 8px;
            background: #fff;
        }

        .sereno-jogador-nome {
            font-size: 1.05rem;
            font-weight: 800;
        }

        .sereno-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            color: #fff;
            font-size: 0.78rem;
            font-weight: 800;
            margin-left: 8px;
        }

        .sereno-meta {
            color: #374151;
            font-weight: 700;
            font-size: 0.92rem;
        }

        div[data-testid="stForm"] {
            background: #ffffff;
            border: 1px solid #ececec;
            border-radius: 18px;
            padding: 14px 14px 8px 14px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.04);
        }

        div[data-testid="stSidebar"] div[data-testid="stForm"] .stTextInput div[data-baseweb="input"] {
            background-color: #ffffff !important;
            border: 2px solid #d1d5db !important;
            border-radius: 12px !important;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05) !important;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        div[data-testid="stSidebar"] div[data-testid="stForm"] .stTextInput div[data-baseweb="input"]:focus-within {
            border-color: #3b82f6 !important;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05), 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
        }

        div.stButton > button { border-radius: 12px !important; font-weight: 700 !important; }
        div[data-baseweb="select"] > div { border-radius: 12px !important; }

        .stTabs [data-baseweb="tab-list"] { gap: 10px; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] { height: 44px; border-radius: 12px 12px 0 0; }
        button[data-baseweb="tab"] p, div[data-testid="stTabs"] button p { font-size: 1.05rem !important; }

        div[data-testid="stCheckbox"] {
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid #efefef;
            margin-bottom: 6px;
            background: #ffffff;
        }

        div[data-testid="stCheckbox"] label p {
            font-weight: 700 !important;
            font-size: 1.05rem !important;
        }

        div.element-container:has(#btn-salvar-presenca),
        div.element-container:has(#btn-marcar-sim),
        div.element-container:has(#btn-marcar-nao),
        div.element-container:has(#btn-atualizar-dados),
        div.element-container:has(#btn-sortear),
        div.element-container:has(#btn-limpar),
        div.element-container:has(#btn-atualizar-presenca),
        div.element-container:has(#btn-salvar-jogador),
        div.element-container:has(#btn-atualizar-jogador),
        div.element-container:has(#btn-excluir-jogador),
        div.element-container:has(#btn-confirmar-exclusao),
        div.element-container:has(#btn-cancelar-exclusao),
        div.element-container:has(#btn-autorizar-senha),
        div.element-container:has(#btn-cancelar-senha),
        div.element-container:has(#btn-whatsapp),
        div.element-container:has(#btn-confirmar-sorteio),
        div.element-container:has(#btn-cancelar-sorteio),
        div.element-container:has(#btn-torneio-capitaes-auto),
        div.element-container:has(#btn-torneio-sortear),
        div.element-container:has(#btn-torneio-limpar),
        div.element-container:has(#btn-whatsapp-torneio) {
            display: none !important;
        }

        div.element-container:has(#btn-atualizar-presenca) + div.element-container div.stButton > button,
        div.element-container:has(#btn-atualizar-dados) + div.element-container div.stButton > button {
            background-color: #f3f4f6 !important; border-color: #e5e7eb !important; color: #1f2937 !important;
        }

        div.element-container:has(#btn-salvar-presenca) + div.element-container div.stButton > button,
        div.element-container:has(#btn-salvar-jogador) + div.element-container button,
        div.element-container:has(#btn-autorizar-senha) + div.element-container button,
        div.element-container:has(#btn-torneio-capitaes-auto) + div.element-container button {
            background-color: #d1fae5 !important; border-color: #a7f3d0 !important; color: #065f46 !important;
        }

        div.element-container:has(#btn-marcar-sim) + div.element-container div.stButton > button,
        div.element-container:has(#btn-atualizar-jogador) + div.element-container button {
            background-color: #dbeafe !important; border-color: #bfdbfe !important; color: #1e40af !important;
        }

        div.element-container:has(#btn-marcar-nao) + div.element-container div.stButton > button,
        div.element-container:has(#btn-excluir-jogador) + div.element-container button,
        div.element-container:has(#btn-confirmar-exclusao) + div.element-container button,
        div.element-container:has(#btn-torneio-limpar) + div.element-container button {
            background-color: #fee2e2 !important; border-color: #fecaca !important; color: #991b1b !important;
        }

        div.element-container:has(#btn-sortear) + div.element-container div.stButton > button,
        div.element-container:has(#btn-confirmar-sorteio) + div.element-container button,
        div.element-container:has(#btn-torneio-sortear) + div.element-container button {
            background-color: #fef08a !important; border-color: #fde047 !important; color: #854d0e !important;
        }

        div.element-container:has(#btn-limpar) + div.element-container div.stButton > button,
        div.element-container:has(#btn-cancelar-exclusao) + div.element-container button,
        div.element-container:has(#btn-cancelar-sorteio) + div.element-container button,
        div.element-container:has(#btn-cancelar-senha) + div.element-container button {
            background-color: #f3f4f6 !important; border-color: #e5e7eb !important; color: #1f2937 !important;
        }

        div.element-container:has(#btn-whatsapp) + div.element-container a,
        div.element-container:has(#btn-whatsapp-torneio) + div.element-container a {
            background-color: #25D366 !important;
            border-color: #128C7E !important;
            color: #ffffff !important;
            border-radius: 12px !important;
        }

        div.element-container:has(#btn-whatsapp) + div.element-container a p,
        div.element-container:has(#btn-whatsapp-torneio) + div.element-container a p {
            color: #ffffff !important;
            font-weight: 800 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def formatar_opcao_vazia(texto):
    return "Selecione..." if texto == "" else texto


def render_table_html(df, centralizar_colunas=None):
    if df.empty:
        return "<div class='sereno-tabela-wrapper'><table class='sereno-table'><tbody><tr><td>Sem dados.</td></tr></tbody></table></div>"

    centralizar_colunas = centralizar_colunas or []

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
            valor = "" if pd.isna(row[col]) else str(row[col])
            classe = "sereno-centralizado" if col in centralizar_colunas else ""
            if is_reserva and col in ["Time A", "Time B"] and valor.strip():
                valor = f"<span style='color:#dc2626;font-weight:bold;'>{valor}</span>"
            linhas_html += f"<td class='{classe}'>{valor}</td>"
        linhas_html += "</tr>"

    return f"""
    <div class="sereno-tabela-wrapper">
        <table class="sereno-table">
            <thead><tr>{colunas_html}</tr></thead>
            <tbody>{linhas_html}</tbody>
        </table>
    </div>
    """


def exibir_tabela_html(df, centralizar_colunas=None):
    st.markdown(render_table_html(df, centralizar_colunas), unsafe_allow_html=True)


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
                    time.sleep(espera_inicial * (2 ** tentativa))
                    continue
            raise


# ==========================================================
# FUNÇÕES DE TEMPO
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


def adicionar_meses(dt, meses):
    ano = dt.year + ((dt.month - 1 + meses) // 12)
    mes = ((dt.month - 1 + meses) % 12) + 1
    dia = min(dt.day, calendar.monthrange(ano, mes)[1])
    return dt.replace(year=ano, month=mes, day=dia)


def formatar_data_hora_br(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M:%S")


# ==========================================================
# WHATSAPP
# ==========================================================
def _gerar_texto_whatsapp_generico(df_sorteio, titulo):
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

    linhas = [titulo]
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
    texto = _gerar_texto_whatsapp_generico(df_sorteio, "🏆 *Resumo do Sorteio - Sereno F.C.*")
    return f"https://wa.me/?text={urllib.parse.quote(texto)}"


def gerar_link_whatsapp_torneio(df_sorteio):
    texto = _gerar_texto_whatsapp_generico(df_sorteio, "🏆 *Resumo do Sorteio do Torneio - Sereno F.C.*")
    return f"https://wa.me/?text={urllib.parse.quote(texto)}"


# ==========================================================
# CONEXÃO / PLANILHA
# ==========================================================
@st.cache_resource
def conectar_gsheet():
    creds = Credentials.from_service_account_info(INFO_CREDENCIAIS, scopes=SCOPES)
    client = gspread.authorize(creds)
    return executar_com_retry(client.open, NOME_PLANILHA)


def obter_mapa_abas_atualizado(planilha):
    worksheets = executar_com_retry(planilha.worksheets)
    return {ws.title: ws for ws in worksheets}


def obter_worksheet(mapa_abas, nome_aba):
    if nome_aba not in mapa_abas:
        raise ValueError(f"A aba '{nome_aba}' não foi encontrada na planilha.")
    return mapa_abas[nome_aba]


def limpar_cache_planilha():
    ler_valores_aba_cacheado.clear()


@st.cache_data(ttl=15)
def ler_valores_aba_cacheado(nome_aba):
    planilha = conectar_gsheet()
    mapa_abas = obter_mapa_abas_atualizado(planilha)
    ws = obter_worksheet(mapa_abas, nome_aba)
    return executar_com_retry(ws.get_all_values)


def ler_valores_aba_tempo_real(mapa_abas, nome_aba):
    ws = obter_worksheet(mapa_abas, nome_aba)
    return executar_com_retry(ws.get_all_values)


# ==========================================================
# LEITURA / ESCRITA
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
    return df[colunas_esperadas].fillna("")


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


def migrar_df_cadastro_para_novo_modelo(df_existente):
    if df_existente is None or df_existente.empty:
        return pd.DataFrame(columns=COLUNAS_CADASTRO)

    df = df_existente.copy()
    for col in COLUNAS_CADASTRO:
        if col not in df.columns:
            df[col] = ""

    if "CONVIDADO" in df.columns and "CONVIDADO_1" in df.columns:
        df["CONVIDADO_1"] = df["CONVIDADO_1"].where(df["CONVIDADO_1"].astype(str).str.strip() != "", df["CONVIDADO"])
    if "CRIANÇA" in df.columns and "CONVIDADO_2" in df.columns:
        df["CONVIDADO_2"] = df["CONVIDADO_2"].where(df["CONVIDADO_2"].astype(str).str.strip() != "", df["CRIANÇA"])

    for col in ["DIRETORIA", "MENSALISTA", "DIARISTA", "CONVIDADO_1", "CONVIDADO_2", "POSICAO", "NOME"]:
        if col not in df.columns:
            df[col] = ""

    return df[COLUNAS_CADASTRO].fillna("")


def inicializar_abas_se_necessario(planilha):
    mapa_abas = obter_mapa_abas_atualizado(planilha)
    configuracoes = [
        (ABA_CADASTRO, COLUNAS_CADASTRO),
        (ABA_PRESENCA, COLUNAS_PRESENCA),
        (ABA_SORTEIO, COLUNAS_SORTEIO),
        (ABA_TORNEIO_DADOS, COLUNAS_TORNEIO_DADOS),
        (ABA_TORNEIO_SORTEIO, COLUNAS_TORNEIO_SORTEIO),
    ]

    for nome_aba, colunas in configuracoes:
        if nome_aba not in mapa_abas:
            executar_com_retry(planilha.add_worksheet, title=nome_aba, rows=300, cols=max(len(colunas), 2))
            mapa_abas = obter_mapa_abas_atualizado(planilha)

        ws = obter_worksheet(mapa_abas, nome_aba)
        valores = executar_com_retry(ws.get_all_values)

        if not valores:
            executar_com_retry(ws.update, "A1", [colunas])
            continue

        cabecalho_atual = valores[0]
        if cabecalho_atual == colunas:
            continue

        linhas = valores[1:] if len(valores) > 1 else []
        if nome_aba == ABA_CADASTRO:
            df_old = pd.DataFrame(linhas, columns=cabecalho_atual) if linhas else pd.DataFrame(columns=cabecalho_atual)
            df_novo = migrar_df_cadastro_para_novo_modelo(df_old)
            novos_valores = [colunas] + df_novo.astype(str).values.tolist()
        else:
            novos_valores = [colunas]
            for linha in linhas:
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
# REGRAS DE NEGÓCIO
# ==========================================================
def normalizar_nome(nome):
    return str(nome).strip()


def normalizar_posicao(posicao):
    p = str(posicao).strip().upper()
    return p if p in OPCOES_POSICAO else ""


def normalizar_categoria(categoria):
    c = str(categoria).strip().upper()
    return c if c in OPCOES_CATEGORIA else ""


def cor_categoria(categoria):
    return MAPA_CORES_CATEGORIA.get(categoria, "#374151")


def montar_linha_cadastro(nome, categoria, posicao):
    return {
        "NOME": nome,
        "DIRETORIA": "SIM" if categoria == "DIRETORIA" else "NÃO",
        "MENSALISTA": "SIM" if categoria == "MENSALISTA" else "NÃO",
        "DIARISTA": "SIM" if categoria == "DIARISTA" else "NÃO",
        "CONVIDADO_1": "SIM" if categoria == "CONVIDADO_1" else "NÃO",
        "CONVIDADO_2": "SIM" if categoria == "CONVIDADO_2" else "NÃO",
        "POSICAO": posicao,
    }


def descobrir_categoria_jogador(linha):
    ordem = ["DIRETORIA", "MENSALISTA", "DIARISTA", "CONVIDADO_1", "CONVIDADO_2"]
    for categoria in ordem:
        if str(linha.get(categoria, "")).upper().strip() == "SIM":
            return categoria
    return ""


def chave_checkbox_presenca(nome):
    return f"presenca_checkbox::{normalizar_nome(nome)}"


def obter_df_cadastro_tratado(mapa_abas):
    df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
    df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
    df_cadastro["POSICAO"] = df_cadastro["POSICAO"].astype(str).str.strip()
    df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

    if not df_cadastro.empty:
        df_cadastro = df_cadastro.drop_duplicates(subset=["NOME"], keep="first").reset_index(drop=True)
    return df_cadastro


def obter_df_presenca_tratado(mapa_abas):
    df_presenca = ler_aba_com_cabecalho(mapa_abas, ABA_PRESENCA, COLUNAS_PRESENCA)
    df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()
    df_presenca["PRESENCA"] = df_presenca["PRESENCA"].astype(str).str.upper().str.strip()
    df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

    if not df_presenca.empty:
        df_presenca = df_presenca.drop_duplicates(subset=["NOME"], keep="first").reset_index(drop=True)
    return df_presenca


def obter_ultimo_timestamp_sorteio_aba(mapa_abas, nome_aba, colunas):
    valores = ler_valores_aba_tempo_real(mapa_abas, nome_aba)
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


def obter_segundos_restantes_bloqueio_sorteio(mapa_abas):
    ultimo_dt = obter_ultimo_timestamp_sorteio_aba(mapa_abas, ABA_SORTEIO, COLUNAS_SORTEIO)
    if ultimo_dt is None:
        return 0
    diferenca = (agora_br() - ultimo_dt).total_seconds()
    return max(0, TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS - int(diferenca))


def formatar_tempo_restante(segundos):
    minutos = int(segundos // 60)
    segundos_restantes = int(segundos % 60)
    return f"{minutos:02d}:{segundos_restantes:02d}"


def montar_df_presenca_sincronizado(mapa_abas):
    df_cadastro = obter_df_cadastro_tratado(mapa_abas)
    df_presenca = obter_df_presenca_tratado(mapa_abas)

    nomes_cadastro = [normalizar_nome(x) for x in df_cadastro["NOME"].tolist() if normalizar_nome(x)]
    presenca_atual = {}
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome and nome not in presenca_atual:
            presenca_atual[nome] = str(row["PRESENCA"]).upper().strip() or "NÃO"

    novas_linhas = [{"NOME": nome, "PRESENCA": presenca_atual.get(nome, "NÃO")} for nome in nomes_cadastro]
    novo_df_presenca = pd.DataFrame(novas_linhas, columns=COLUNAS_PRESENCA)
    return novo_df_presenca, df_presenca


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
        linhas.append({"NOME": nome, "PRESENCA": "SIM" if marcado else "NÃO"})
    return pd.DataFrame(linhas, columns=COLUNAS_PRESENCA)


def distribuir_grupo_para_listas(itens_embaralhados, time_a, time_b):
    proximo_time = 1 if len(time_a) <= len(time_b) else 2
    for item in itens_embaralhados:
        if proximo_time == 1:
            time_a.append(item)
            proximo_time = 2
        else:
            time_b.append(item)
            proximo_time = 1


def montar_cadastro_map(df_cadastro):
    cadastro_map = {}
    for _, row in df_cadastro.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome and nome not in cadastro_map:
            cadastro_map[nome] = {
                "categoria": descobrir_categoria_jogador(row.to_dict()),
                "posicao": normalizar_posicao(row.to_dict().get("POSICAO", "")),
            }
    return cadastro_map


def sortear_times_core(df_cadastro, df_presenca, nomes_fixos_time_a=None, nomes_fixos_time_b=None):
    nomes_fixos_time_a = [normalizar_nome(x) for x in (nomes_fixos_time_a or []) if normalizar_nome(x)]
    nomes_fixos_time_b = [normalizar_nome(x) for x in (nomes_fixos_time_b or []) if normalizar_nome(x)]

    cadastro_map = montar_cadastro_map(df_cadastro)

    presentes = []
    ja_incluidos = set()

    def montar_obj(nome, fixo=False):
        info = cadastro_map[nome]
        return {
            "nome": nome,
            "categoria": info["categoria"],
            "posicao": info["posicao"],
            "fixo": fixo,
        }

    time_a_objs = []
    time_b_objs = []

    nomes_presentes = set(
        normalizar_nome(row["NOME"])
        for _, row in df_presenca.iterrows()
        if str(row["PRESENCA"]).upper().strip() == "SIM" and normalizar_nome(row["NOME"]) in cadastro_map
    )

    for nome in nomes_fixos_time_a:
        if nome in nomes_presentes and nome in cadastro_map and nome not in ja_incluidos:
            time_a_objs.append(montar_obj(nome, fixo=True))
            ja_incluidos.add(nome)

    for nome in nomes_fixos_time_b:
        if nome in nomes_presentes and nome in cadastro_map and nome not in ja_incluidos:
            time_b_objs.append(montar_obj(nome, fixo=True))
            ja_incluidos.add(nome)

    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        presenca = str(row["PRESENCA"]).upper().strip()
        if nome and presenca == "SIM" and nome in cadastro_map and nome not in ja_incluidos:
            presentes.append(montar_obj(nome, fixo=False))
            ja_incluidos.add(nome)

    ordem_categorias = ["DIRETORIA", "MENSALISTA", "DIARISTA", "CONVIDADO_1", "CONVIDADO_2"]
    grupos = {categoria: [] for categoria in ordem_categorias}
    for jogador in presentes:
        if jogador["categoria"] in grupos:
            grupos[jogador["categoria"]].append(jogador)

    for categoria in grupos:
        random.shuffle(grupos[categoria])

    for categoria in ordem_categorias:
        jogadores_grupo = grupos[categoria]
        if jogadores_grupo:
            distribuir_grupo_para_listas(jogadores_grupo, time_a_objs, time_b_objs)

    for i, obj in enumerate(time_a_objs):
        obj["status"] = 1 if i < 11 else 2
    for i, obj in enumerate(time_b_objs):
        obj["status"] = 1 if i < 11 else 2

    ordem_cat = {"DIRETORIA": 1, "MENSALISTA": 2, "DIARISTA": 3, "CONVIDADO_1": 4, "CONVIDADO_2": 5}
    ordem_pos = {"ZAGUEIRO": 1, "MEIO CAMPO": 2, "ATACANTE": 3}

    def ordenar_time(lista, nomes_fixos):
        fixos = [obj for obj in lista if obj.get("fixo")]
        restantes = [obj for obj in lista if not obj.get("fixo")]
        fixos_por_nome = {obj["nome"]: obj for obj in fixos}
        fixos_ordenados = [fixos_por_nome[nome] for nome in nomes_fixos if nome in fixos_por_nome]

        restantes.sort(
            key=lambda jogador: (
                jogador.get("status", 2),
                ordem_cat.get(jogador["categoria"], 99),
                ordem_pos.get(jogador["posicao"], 99),
                jogador["nome"],
            )
        )
        return fixos_ordenados + restantes

    time_a_ordenado = ordenar_time(time_a_objs, nomes_fixos_time_a)
    time_b_ordenado = ordenar_time(time_b_objs, nomes_fixos_time_b)

    time_a = [obj["nome"] for obj in time_a_ordenado if str(obj["nome"]).strip()]
    time_b = [obj["nome"] for obj in time_b_ordenado if str(obj["nome"]).strip()]

    max_len = max(len(time_a), len(time_b))
    linhas_sorteio = []
    for i in range(max_len):
        linhas_sorteio.append(
            {
                "Ordem": str(i + 1),
                "Time A": time_a[i] if i < len(time_a) else "",
                "Time B": time_b[i] if i < len(time_b) else "",
            }
        )

    return pd.DataFrame(linhas_sorteio, columns=["Ordem", "Time A", "Time B"])


def anexar_timestamp_sorteio(df_sorteio, timestamp_str, colunas_saida):
    df_sorteio = df_sorteio.copy()
    if df_sorteio.empty:
        return pd.DataFrame([{"Ordem": "", "Time A": "", "Time B": "", "SORTEIO": timestamp_str}], columns=colunas_saida)

    df_sorteio["SORTEIO"] = ""
    df_sorteio.at[0, "SORTEIO"] = timestamp_str
    return df_sorteio[colunas_saida]


def realizar_limpeza_sorteio_normal(mapa_abas, msg_sucesso="Sorteio limpo com sucesso."):
    ultimo_dt = obter_ultimo_timestamp_sorteio_aba(mapa_abas, ABA_SORTEIO, COLUNAS_SORTEIO)
    timestamp_str = formatar_timestamp_sorteio(ultimo_dt) if ultimo_dt else ""

    if timestamp_str:
        df_vazio = pd.DataFrame([{"Ordem": "", "Time A": "", "Time B": "", "SORTEIO": timestamp_str}], columns=COLUNAS_SORTEIO)
    else:
        df_vazio = pd.DataFrame(columns=COLUNAS_SORTEIO)

    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_vazio, COLUNAS_SORTEIO)
    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""
    st.success(msg_sucesso)
    st.rerun()


def realizar_sorteio_normal(mapa_abas):
    df_cadastro = obter_df_cadastro_tratado(mapa_abas)
    df_presenca = obter_df_presenca_tratado(mapa_abas)
    presentes_sim = df_presenca[df_presenca["PRESENCA"] == "SIM"]

    if df_cadastro.empty:
        st.error("Não há jogadores cadastrados.")
        return
    if df_presenca.empty:
        st.error("A lista de presença está vazia.")
        return
    if presentes_sim.empty:
        realizar_limpeza_sorteio_normal(mapa_abas, msg_sucesso="Sorteio limpo, pois nenhum jogador foi marcado como presente.")
        return

    df_sorteio = sortear_times_core(df_cadastro, df_presenca)
    timestamp_atual = formatar_timestamp_sorteio(agora_br())
    df_sorteio = anexar_timestamp_sorteio(df_sorteio, timestamp_atual, COLUNAS_SORTEIO)
    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_sorteio, COLUNAS_SORTEIO)

    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""
    st.session_state.confirmar_sorteio_pendente = False

    st.success("Sorteio realizado com sucesso.")
    st.rerun()


# ==========================================================
# TORNEIO - DADOS E REGRAS
# ==========================================================
def ler_dados_torneio(mapa_abas):
    df = ler_aba_com_cabecalho(mapa_abas, ABA_TORNEIO_DADOS, COLUNAS_TORNEIO_DADOS)
    df["CHAVE"] = df["CHAVE"].astype(str).str.strip()
    df["VALOR"] = df["VALOR"].astype(str).str.strip()
    df = df[df["CHAVE"] != ""].reset_index(drop=True)
    if not df.empty:
        df = df.drop_duplicates(subset=["CHAVE"], keep="last").reset_index(drop=True)
    return df


def obter_valor_torneio(mapa_abas, chave):
    df = ler_dados_torneio(mapa_abas)
    linha = df[df["CHAVE"] == chave]
    if linha.empty:
        return ""
    return str(linha.iloc[0]["VALOR"]).strip()


def salvar_valor_torneio(mapa_abas, chave, valor):
    df = ler_dados_torneio(mapa_abas)
    if chave in df["CHAVE"].tolist():
        idx = df.index[df["CHAVE"] == chave][0]
        df.at[idx, "VALOR"] = str(valor)
    else:
        df = pd.concat([df, pd.DataFrame([{"CHAVE": chave, "VALOR": str(valor)}])], ignore_index=True)
    escrever_dataframe_na_aba(mapa_abas, ABA_TORNEIO_DADOS, df, COLUNAS_TORNEIO_DADOS)


def limpar_dados_torneio(mapa_abas):
    escrever_dataframe_na_aba(mapa_abas, ABA_TORNEIO_DADOS, pd.DataFrame(columns=COLUNAS_TORNEIO_DADOS), COLUNAS_TORNEIO_DADOS)
    escrever_dataframe_na_aba(mapa_abas, ABA_TORNEIO_SORTEIO, pd.DataFrame(columns=COLUNAS_TORNEIO_SORTEIO), COLUNAS_TORNEIO_SORTEIO)


def obter_capitaes_torneio(mapa_abas):
    return (
        obter_valor_torneio(mapa_abas, CHAVE_TORNEIO_CAPITAO_A),
        obter_valor_torneio(mapa_abas, CHAVE_TORNEIO_CAPITAO_B),
    )


def obter_dt_ultimo_sorteio_torneio(mapa_abas):
    texto = obter_valor_torneio(mapa_abas, CHAVE_TORNEIO_DATA_ULTIMO_SORTEIO)
    return parse_timestamp_sorteio(texto)


def selecionar_capitaes_automaticamente(mapa_abas):
    df_cadastro = obter_df_cadastro_tratado(mapa_abas)
    df_diretoria = df_cadastro[df_cadastro.apply(lambda row: descobrir_categoria_jogador(row.to_dict()) == "DIRETORIA", axis=1)].copy()

    nomes = [normalizar_nome(x) for x in df_diretoria["NOME"].tolist() if normalizar_nome(x)]
    if len(nomes) < 2:
        st.error("É necessário ter pelo menos 2 jogadores da categoria DIRETORIA para selecionar capitães.")
        return

    cap_a, cap_b = random.sample(nomes, 2)
    salvar_valor_torneio(mapa_abas, CHAVE_TORNEIO_CAPITAO_A, cap_a)
    salvar_valor_torneio(mapa_abas, CHAVE_TORNEIO_CAPITAO_B, cap_b)
    st.success(f"Capitães definidos automaticamente: {cap_a} e {cap_b}.")
    st.rerun()


def obter_dt_proximo_sorteio_torneio(mapa_abas):
    ultimo = obter_dt_ultimo_sorteio_torneio(mapa_abas)
    if not ultimo:
        return None
    return adicionar_meses(ultimo, BLOQUEIO_TORNEIO_MESES)


def sortear_torneio(mapa_abas):
    cap_a, cap_b = obter_capitaes_torneio(mapa_abas)
    if not cap_a or not cap_b:
        st.error("Defina os capitães automaticamente antes de realizar o sorteio do torneio.")
        return
    if cap_a == cap_b:
        st.error("Os capitães do torneio não podem ser iguais.")
        return

    df_cadastro = obter_df_cadastro_tratado(mapa_abas)
    df_presenca = obter_df_presenca_tratado(mapa_abas)

    if df_cadastro.empty:
        st.error("Não há jogadores cadastrados.")
        return
    if df_presenca.empty:
        st.error("A lista de presença está vazia.")
        return

    nomes_presentes = set(df_presenca[df_presenca["PRESENCA"] == "SIM"]["NOME"].tolist())
    if cap_a not in nomes_presentes or cap_b not in nomes_presentes:
        faltando = []
        if cap_a not in nomes_presentes:
            faltando.append(cap_a)
        if cap_b not in nomes_presentes:
            faltando.append(cap_b)
        st.error("Os capitães precisam estar marcados como presentes para o sorteio do torneio: " + ", ".join(faltando))
        return

    presentes_sim = df_presenca[df_presenca["PRESENCA"] == "SIM"]
    if presentes_sim.empty:
        st.error("Nenhum jogador está marcado como presente.")
        return

    df_sorteio = sortear_times_core(df_cadastro, df_presenca, nomes_fixos_time_a=[cap_a], nomes_fixos_time_b=[cap_b])
    timestamp_atual = formatar_timestamp_sorteio(agora_br())
    df_sorteio = anexar_timestamp_sorteio(df_sorteio, timestamp_atual, COLUNAS_TORNEIO_SORTEIO)
    escrever_dataframe_na_aba(mapa_abas, ABA_TORNEIO_SORTEIO, df_sorteio, COLUNAS_TORNEIO_SORTEIO)
    salvar_valor_torneio(mapa_abas, CHAVE_TORNEIO_DATA_ULTIMO_SORTEIO, timestamp_atual)
    st.success("Sorteio do torneio realizado com sucesso.")
    st.rerun()


def limpar_sorteio_torneio(mapa_abas):
    limpar_dados_torneio(mapa_abas)
    st.success("Sorteio do torneio limpo com sucesso.")
    st.rerun()


# ==========================================================
# ESTADO INICIAL
# ==========================================================
defaults = {
    "abas_inicializadas": False,
    "admin_autenticado": False,
    "admin_erro_login": "",
    "exigir_senha_master_acao": False,
    "erro_senha_master_acao": "",
    "tipo_acao_pendente": "",
    "pendente_excluir_jogador": "",
    "forcar_atualizacao_presenca": False,
    "confirmar_sorteio_pendente": False,
}
for chave, valor in defaults.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor

# ==========================================================
# ESTILO
# ==========================================================
aplicar_estilo_global()

# ==========================================================
# SIDEBAR - LOGIN ADMIN
# ==========================================================
with st.sidebar:
    st.header("ACESSO AO SISTEMA SERENO")

    if not st.session_state.admin_autenticado:
        with st.form("form_login_admin", clear_on_submit=True):
            usuario_admin = st.text_input("Usuário", placeholder="Digite o usuário...")
            senha_admin = st.text_input("Senha", type="password", placeholder="Digite a senha...")
            entrar_admin = st.form_submit_button("Entrar")

        if entrar_admin:
            if usuario_admin == ADMIN_USUARIO and senha_admin == ADMIN_SENHA:
                st.session_state.admin_autenticado = True
                st.session_state.admin_erro_login = ""
                st.session_state.forcar_atualizacao_presenca = True
                st.rerun()
            else:
                st.session_state.admin_erro_login = "Usuário ou Senha inválidos!"

        if st.session_state.admin_erro_login:
            st.error(st.session_state.admin_erro_login)
        st.info("Faça Login para acessar os dados!")
    else:
        st.success("Login Autenticado.")
        st.write(f"Usuário: {ADMIN_USUARIO}")
        if st.button("Sair", use_container_width=True):
            st.session_state.admin_autenticado = False
            st.session_state.admin_erro_login = ""
            st.rerun()

# ==========================================================
# TOPO
# ==========================================================
st.markdown(
    """
    <div class="sereno-topo">
        <p class="sereno-titulo">Sereno F.C.</p>
        <p class="sereno-subtitulo">Sistema de cadastro, presença e sorteio de times</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==========================================================
# APP
# ==========================================================
try:
    planilha = conectar_gsheet()

    if not st.session_state.abas_inicializadas:
        inicializar_abas_se_necessario(planilha)
        st.session_state.abas_inicializadas = True

    mapa_abas = obter_mapa_abas_atualizado(planilha)

    abas = st.tabs([
        "CADASTRO        ",
        "JOGADORES        ",
        "PRESENÇA        ",
        "SORTEIO        ",
        "TORNEIO",
    ])

    # ======================================================
    # ABA 1 - CADASTRO
    # ======================================================
    with abas[0]:
        df_cadastro = obter_df_cadastro_tratado(mapa_abas)

        if st.session_state.admin_autenticado:
            st.markdown("### Adicionar jogador")
            with st.form("form_cadastro", clear_on_submit=True):
                nome_jogador = st.text_input("Nome do jogador")
                posicao = st.selectbox("Posição", [""] + OPCOES_POSICAO, format_func=formatar_opcao_vazia)
                categoria = st.selectbox("Categoria", [""] + OPCOES_CATEGORIA, format_func=formatar_opcao_vazia)
                st.markdown('<div id="btn-salvar-jogador" style="display:none;"></div>', unsafe_allow_html=True)
                enviar_cadastro = st.form_submit_button("Salvar jogador")

            if enviar_cadastro:
                nome_jogador = normalizar_nome(nome_jogador)
                posicao = normalizar_posicao(posicao)
                categoria = normalizar_categoria(categoria)

                if not nome_jogador:
                    st.error("Informe o nome do jogador.")
                elif not posicao:
                    st.error("Selecione a posição.")
                elif not categoria:
                    st.error("Selecione a categoria.")
                elif nome_jogador.upper() in [x.upper() for x in df_cadastro["NOME"].tolist()]:
                    st.error("Esse jogador já está cadastrado.")
                else:
                    nova_linha = montar_linha_cadastro(nome_jogador, categoria, posicao)
                    df_cadastro = pd.concat([df_cadastro, pd.DataFrame([nova_linha])], ignore_index=True)
                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                    st.success("Jogador cadastrado com sucesso.")
                    st.rerun()

            st.markdown("### Atualizar jogador")
            nomes_existentes = [""] + df_cadastro["NOME"].tolist()
            with st.form("form_editar", clear_on_submit=True):
                jogador_editar = st.selectbox("Selecione o jogador", nomes_existentes, format_func=formatar_opcao_vazia)
                posicao_editar = st.selectbox("Nova posição", [""] + OPCOES_POSICAO, format_func=formatar_opcao_vazia)
                categoria_editar = st.selectbox("Nova categoria", [""] + OPCOES_CATEGORIA, format_func=formatar_opcao_vazia)
                st.markdown('<div id="btn-atualizar-jogador" style="display:none;"></div>', unsafe_allow_html=True)
                salvar_edicao = st.form_submit_button("Atualizar jogador")

            if salvar_edicao:
                if not jogador_editar:
                    st.error("Selecione o jogador.")
                elif not posicao_editar:
                    st.error("Selecione a nova posição.")
                elif not categoria_editar:
                    st.error("Selecione a nova categoria.")
                else:
                    idx = df_cadastro.index[df_cadastro["NOME"] == jogador_editar][0]
                    linha_atualizada = montar_linha_cadastro(
                        jogador_editar,
                        normalizar_categoria(categoria_editar),
                        normalizar_posicao(posicao_editar),
                    )
                    for col in COLUNAS_CADASTRO:
                        df_cadastro.at[idx, col] = linha_atualizada[col]
                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                    st.success("Jogador atualizado com sucesso.")
                    st.rerun()

            st.markdown("### Excluir jogador")
            with st.form("form_excluir", clear_on_submit=True):
                jogador_excluir = st.selectbox(
                    "Selecione o jogador para excluir",
                    nomes_existentes,
                    format_func=formatar_opcao_vazia,
                    key="excluir_jogador",
                )
                st.markdown('<div id="btn-excluir-jogador" style="display:none;"></div>', unsafe_allow_html=True)
                excluir = st.form_submit_button("Excluir jogador")

            if excluir:
                if not jogador_excluir:
                    st.error("Selecione o jogador para excluir.")
                else:
                    st.session_state.pendente_excluir_jogador = jogador_excluir
                    st.rerun()

            if st.session_state.pendente_excluir_jogador:
                with st.container(border=True):
                    st.warning(f"Deseja realmente excluir o jogador '{st.session_state.pendente_excluir_jogador}'?")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown('<div id="btn-confirmar-exclusao" style="display:none;"></div>', unsafe_allow_html=True)
                        if st.button("Confirmar exclusão", use_container_width=True):
                            jogador_alvo = st.session_state.pendente_excluir_jogador
                            df_cadastro = df_cadastro[df_cadastro["NOME"] != jogador_alvo].reset_index(drop=True)
                            escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                            sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                            st.session_state.pendente_excluir_jogador = ""
                            st.success("Jogador excluído com sucesso.")
                            st.rerun()
                    with c2:
                        st.markdown('<div id="btn-cancelar-exclusao" style="display:none;"></div>', unsafe_allow_html=True)
                        if st.button("Cancelar exclusão", use_container_width=True):
                            st.session_state.pendente_excluir_jogador = ""
                            st.rerun()
        else:
            st.warning("Área de Edição restrita ao Adm.!")

    # ======================================================
    # ABA 2 - JOGADORES
    # ======================================================
    with abas[1]:
        df_cadastro = obter_df_cadastro_tratado(mapa_abas)

        if df_cadastro.empty:
            st.info("Nenhum jogador cadastrado ainda.")
        else:
            st.markdown("<div class='sereno-card-jogadores'>", unsafe_allow_html=True)
            for idx, row in df_cadastro.iterrows():
                nome = normalizar_nome(row["NOME"])
                categoria = descobrir_categoria_jogador(row.to_dict())
                posicao = normalizar_posicao(row.get("POSICAO", ""))
                cor = cor_categoria(categoria)

                col1, col2 = st.columns([5, 1.4])
                with col1:
                    st.markdown(
                        f"""
                        <div class="sereno-jogador-linha">
                            <div>
                                <span class="sereno-jogador-nome" style="color:{cor};">{nome}</span>
                                <span class="sereno-pill" style="background:{cor};">{categoria or "SEM CATEGORIA"}</span>
                            </div>
                            <div class="sereno-meta">{posicao}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    chave_diarista = f"jogador_diarista::{idx}::{nome}"
                    valor_inicial = categoria == "DIARISTA"
                    marcado = st.checkbox("DIARISTA", value=valor_inicial, key=chave_diarista, disabled=not st.session_state.admin_autenticado)
                    if st.session_state.admin_autenticado and marcado and categoria != "DIARISTA":
                        linha_nova = montar_linha_cadastro(nome, "DIARISTA", posicao)
                        for col in COLUNAS_CADASTRO:
                            df_cadastro.at[idx, col] = linha_nova[col]
                        escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                        sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
                        st.success(f"{nome} agora é exclusivamente DIARISTA.")
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            if not st.session_state.admin_autenticado:
                st.info("O checkbox DIARISTA fica habilitado apenas para o Adm.")

    # ======================================================
    # ABA 3 - PRESENÇA
    # ======================================================
    with abas[2]:
        st.markdown('<div id="btn-atualizar-presenca" style="display:none;"></div>', unsafe_allow_html=True)

        if st.session_state.get("forcar_atualizacao_presenca", False):
            limpar_cache_planilha()
            mapa_abas = obter_mapa_abas_atualizado(planilha)
            df_fresco = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
            aplicar_df_presenca_ao_estado(df_fresco)
            st.session_state.forcar_atualizacao_presenca = False

        if st.button("🔄 Atualizar Presenças", use_container_width=True):
            limpar_cache_planilha()
            mapa_abas = obter_mapa_abas_atualizado(planilha)
            df_fresco = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
            aplicar_df_presenca_ao_estado(df_fresco)
            st.rerun()

        mapa_abas = obter_mapa_abas_atualizado(planilha)
        df_presenca = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
        df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()
        df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

        inicializar_estado_checkboxes_presenca(df_presenca)

        if st.session_state.admin_autenticado:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div id="btn-salvar-presenca" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Salvar Presenças", use_container_width=True):
                    novo_df_presenca = construir_df_presenca_a_partir_dos_checkboxes(df_presenca)
                    escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)
                    aplicar_df_presenca_ao_estado(novo_df_presenca)
                    st.success("Lista de presença salva com sucesso.")
                    st.rerun()

            with col2:
                st.markdown('<div id="btn-marcar-sim" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Marcar Todos", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "SIM"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, True)
                    st.success("Todos os jogadores foram marcados como SIM.")
                    st.rerun()

            with col3:
                st.markdown('<div id="btn-marcar-nao" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Desmarcar Todos", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "NÃO"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, False)
                    st.success("Presenças zeradas com sucesso.")
                    st.rerun()

            if df_presenca.empty:
                st.info("Nenhum jogador disponível na lista de presença. Cadastre jogadores na aba CADASTRO.")
            else:
                st.markdown("<div class='sereno-card-presenca'>", unsafe_allow_html=True)
                for _, row in df_presenca.iterrows():
                    nome = normalizar_nome(row["NOME"])
                    st.checkbox(f"**{nome}**", key=chave_checkbox_presenca(nome))
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Alterações de Presença restritas ao Adm.!")

    # ======================================================
    # ABA 4 - SORTEIO NORMAL
    # ======================================================
    with abas[3]:
        st.markdown('<div id="btn-atualizar-dados" style="display:none;"></div>', unsafe_allow_html=True)
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            limpar_cache_planilha()
            st.rerun()

        mapa_abas = obter_mapa_abas_atualizado(planilha)
        df_sorteio_leitura = ler_aba_com_cabecalho(mapa_abas, ABA_SORTEIO, COLUNAS_SORTEIO)
        df_sorteio_leitura["Ordem"] = df_sorteio_leitura["Ordem"].astype(str).str.strip()
        df_sorteio_valido = df_sorteio_leitura[df_sorteio_leitura["Ordem"] != ""].reset_index(drop=True)
        tem_jogadores_sorteados = not df_sorteio_valido.empty

        if st.session_state.admin_autenticado:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<div id="btn-sortear" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Sortear times", use_container_width=True):
                    st.session_state.confirmar_sorteio_pendente = True
                    st.rerun()

            with col2:
                st.markdown('<div id="btn-limpar" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Limpar sorteio", use_container_width=True):
                    restante = obter_segundos_restantes_bloqueio_sorteio(mapa_abas)
                    if restante <= 0 or not tem_jogadores_sorteados:
                        realizar_limpeza_sorteio_normal(mapa_abas)
                    else:
                        st.session_state.exigir_senha_master_acao = True
                        st.session_state.erro_senha_master_acao = ""
                        st.session_state.tipo_acao_pendente = "limpar"

            if st.session_state.confirmar_sorteio_pendente:
                with st.container(border=True):
                    st.warning("TEM CERTEZA QUE DESEJA FAZER O SORTEIO? OUTRO SORTEIO AUTORIZADO SÓ DAQUI A 10 MINUTOS!")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown('<div id="btn-confirmar-sorteio" style="display:none;"></div>', unsafe_allow_html=True)
                        if st.button("Confirmar sorteio", use_container_width=True):
                            st.session_state.confirmar_sorteio_pendente = False
                            restante = obter_segundos_restantes_bloqueio_sorteio(mapa_abas)
                            if restante <= 0 or not tem_jogadores_sorteados:
                                realizar_sorteio_normal(mapa_abas)
                            else:
                                st.session_state.exigir_senha_master_acao = True
                                st.session_state.erro_senha_master_acao = ""
                                st.session_state.tipo_acao_pendente = "sortear"
                                st.rerun()
                    with c2:
                        st.markdown('<div id="btn-cancelar-sorteio" style="display:none;"></div>', unsafe_allow_html=True)
                        if st.button("Cancelar", use_container_width=True):
                            st.session_state.confirmar_sorteio_pendente = False
                            st.rerun()

            if st.session_state.exigir_senha_master_acao:
                restante = obter_segundos_restantes_bloqueio_sorteio(mapa_abas)
                acao_txt = "novo sorteio" if st.session_state.tipo_acao_pendente == "sortear" else "limpar sorteio"
                st.warning(
                    f"Essa ação só pode ser feita sem senha após 10 minutos. "
                    f"Tempo restante: {formatar_tempo_restante(restante)}. "
                    f"Digite a senha master para autorizar {acao_txt} agora."
                )

                with st.container(border=True):
                    senha_master_digitada = st.text_input("Senha master", type="password", key="senha_master_acao_widget")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown('<div id="btn-autorizar-senha" style="display:none;"></div>', unsafe_allow_html=True)
                        if st.button("Autorizar", use_container_width=True):
                            if senha_master_digitada == SENHA_MASTER_SORTEIO:
                                st.session_state.exigir_senha_master_acao = False
                                st.session_state.erro_senha_master_acao = ""
                                if st.session_state.tipo_acao_pendente == "sortear":
                                    realizar_sorteio_normal(mapa_abas)
                                elif st.session_state.tipo_acao_pendente == "limpar":
                                    realizar_limpeza_sorteio_normal(mapa_abas)
                            else:
                                st.session_state.erro_senha_master_acao = "Senha master inválida."
                    with c2:
                        st.markdown('<div id="btn-cancelar-senha" style="display:none;"></div>', unsafe_allow_html=True)
                        if st.button("Cancelar", use_container_width=True):
                            st.session_state.exigir_senha_master_acao = False
                            st.session_state.erro_senha_master_acao = ""
                            st.session_state.tipo_acao_pendente = ""
                            st.rerun()

                    if st.session_state.erro_senha_master_acao:
                        st.error(st.session_state.erro_senha_master_acao)
        else:
            st.warning("Sortear e limpar sorteio são ações para o Adm.!")

        if not tem_jogadores_sorteados:
            st.info("Ainda não há sorteio realizado!")
        else:
            exibir_tabela_html(df_sorteio_valido[["Ordem", "Time A", "Time B"]], centralizar_colunas=["Ordem", "Time A", "Time B"])
            link_whatsapp = gerar_link_whatsapp_sorteio(df_sorteio_leitura)
            st.markdown('<div id="btn-whatsapp" style="display:none;"></div>', unsafe_allow_html=True)
            st.link_button("RESUMO PARA WHATSAPP", link_whatsapp, use_container_width=True)

    # ======================================================
    # ABA 5 - TORNEIO
    # ======================================================
    with abas[4]:
        mapa_abas = obter_mapa_abas_atualizado(planilha)
        cap_a, cap_b = obter_capitaes_torneio(mapa_abas)
        dt_ultimo_torneio = obter_dt_ultimo_sorteio_torneio(mapa_abas)
        dt_proximo_torneio = obter_dt_proximo_sorteio_torneio(mapa_abas)

        df_torneio_sorteio = ler_aba_com_cabecalho(mapa_abas, ABA_TORNEIO_SORTEIO, COLUNAS_TORNEIO_SORTEIO)
        df_torneio_sorteio["Ordem"] = df_torneio_sorteio["Ordem"].astype(str).str.strip()
        df_torneio_valido = df_torneio_sorteio[df_torneio_sorteio["Ordem"] != ""].reset_index(drop=True)
        tem_torneio_sorteado = not df_torneio_valido.empty

        st.markdown("<div class='sereno-card-torneio'>", unsafe_allow_html=True)
        st.markdown("### Capitães do Torneio")
        st.write(f"**CAPITÃO DO TIME_A:** {cap_a or 'Não definido'}")
        st.write(f"**CAPITÃO DO TIME_B:** {cap_b or 'Não definido'}")

        if dt_ultimo_torneio:
            st.info(
                f"Último sorteio do torneio: {formatar_data_hora_br(dt_ultimo_torneio)}. "
                f"Próximo sorteio sem senha master: {formatar_data_hora_br(dt_proximo_torneio)}."
            )
        else:
            st.info("Ainda não houve sorteio do torneio.")
        st.markdown("</div>", unsafe_allow_html=True)

        senha_torneio_digitada = st.text_input("Senha_torneio", type="password", key="senha_torneio_digitada")
        senha_master_torneio = st.text_input(
            "Senha master (somente para liberar novo sorteio antes de 3 meses ou limpar sorteio)",
            type="password",
            key="senha_master_torneio_digitada",
        )

        if st.session_state.admin_autenticado:
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown('<div id="btn-torneio-capitaes-auto" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("SELECIONAR CAPITÃES AUTOMATICAMENTE", use_container_width=True):
                    if senha_torneio_digitada != SENHA_TORNEIO:
                        st.error("Senha_torneio inválida.")
                    else:
                        selecionar_capitaes_automaticamente(mapa_abas)

            with c2:
                st.markdown('<div id="btn-torneio-sortear" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("SORTEAR TIMES DO TORNEIO", use_container_width=True):
                    if senha_torneio_digitada != SENHA_TORNEIO:
                        st.error("Senha_torneio inválida.")
                    else:
                        liberado = True
                        if dt_proximo_torneio and agora_br() < dt_proximo_torneio:
                            liberado = senha_master_torneio == SENHA_MASTER_SORTEIO
                            if not liberado:
                                st.error("Novo sorteio do torneio só pode ser realizado após 3 meses, salvo com senha master válida.")
                        if liberado:
                            sortear_torneio(mapa_abas)

            with c3:
                st.markdown('<div id="btn-torneio-limpar" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("LIMPAR_SORTEIO", use_container_width=True):
                    if senha_master_torneio != SENHA_MASTER_SORTEIO:
                        st.error("Senha master inválida para limpar o sorteio do torneio.")
                    else:
                        limpar_sorteio_torneio(mapa_abas)
        else:
            st.warning("Ações do torneio restritas ao Adm.!")

        st.markdown("### Resultado do Sorteio do Torneio")
        if not tem_torneio_sorteado:
            st.info("Ainda não há sorteio do torneio realizado!")
        else:
            exibir_tabela_html(df_torneio_valido[["Ordem", "Time A", "Time B"]], centralizar_colunas=["Ordem", "Time A", "Time B"])
            st.markdown('<div id="btn-whatsapp-torneio" style="display:none;"></div>', unsafe_allow_html=True)
            st.link_button("ENVIAR TIMES DO TORNEIO PARA WHATSAPP", gerar_link_whatsapp_torneio(df_torneio_sorteio), use_container_width=True)

    # ======================================================
    # LOGO NO FINAL DA PÁGINA
    # ======================================================
    col_logo_esq, col_logo_centro, col_logo_dir = st.columns([1, 1.5, 1])
    with col_logo_centro:
        logo_path = Path("SERENO FC.png")
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)

    st.markdown(
        "<div style='text-align:center; font-size:1rem; font-weight:600; color:#374151; margin-top:10px;'>App criado por: Teori@ / Sereno FC</div>",
        unsafe_allow_html=True,
    )

except SpreadsheetNotFound:
    st.error("Planilha 'FUTEBOL_SERENO' não encontrada ou não compartilhada com a service account.")
except Exception as e:
    st.error("Erro ao executar a aplicação.")
    st.exception(e)
