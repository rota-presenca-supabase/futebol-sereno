import random
import time
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

COLUNAS_CADASTRO = ["NOME", "MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR", "POSICAO"]
COLUNAS_PRESENCA = ["NOME", "PRESENCA"]
COLUNAS_SORTEIO = ["ORDEM", "Time A", "Time B", "SORTEIO"]

OPCOES_POSICAO = ["ZAGUEIRO", "MEIO CAMPO", "ATACANTE"]
OPCOES_CATEGORIA = ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
FORMATO_SORTEIO = "%Y-%m-%d %H:%M:%S"

# ==========================================================
# ACESSO ADMINISTRADOR
# ==========================================================
ADMIN_USUARIO = "sereno"
ADMIN_SENHA = "sereno"

# ==========================================================
# CONTROLE DE NOVO SORTEIO / LIMPAR SORTEIO
# ==========================================================
TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS = 10 * 60
SENHA_MASTER_SORTEIO = "123"

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
            font-size: 3.0rem !important; /* Reduzido em 40% conforme solicitado */
            font-weight: 900 !important; /* Forçado para negrito máximo */
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
            font-size: 0.97rem;
            table-layout: auto;
        }

        table.sereno-table thead th {
            background: #111827;
            color: #ffffff;
            text-align: center; /* Cabeçalho centralizado */
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

        table.sereno-table tbody tr:nth-child(odd) {
            background: #fafafa;
        }

        table.sereno-table tbody tr:nth-child(even) {
            background: #ffffff;
        }

        table.sereno-table tbody tr:hover {
            background: #fff4e8;
        }

        .sereno-centralizado {
            text-align: center !important;
        }

        .sereno-secao-titulo {
            font-size: 1.12rem;
            font-weight: 700;
            margin-bottom: 10px;
            color: #111827;
        }

        .sereno-logo-rodape {
            width: 100%;
            display: flex;
            justify-content: center !important;
            align-items: center;
            text-align: center;
            margin-top: 28px;
            margin-bottom: 10px;
        }

        .sereno-card-presenca {
            background: linear-gradient(180deg, #fffaf5 0%, #ffffff 100%);
            border: 2px solid #f59e0b;
            border-radius: 18px;
            padding: 16px 18px 10px 18px;
            box-shadow: 0 8px 18px rgba(245, 158, 11, 0.10);
            margin-bottom: 14px;
        }

        div[data-testid="stForm"] {
            background: #ffffff;
            border: 1px solid #ececec;
            border-radius: 18px;
            padding: 14px 14px 8px 14px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.04);
        }

        div.stButton > button {
            border-radius: 12px !important;
            font-weight: 700 !important;
        }

        div[data-baseweb="select"] > div {
            border-radius: 12px !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            flex-wrap: wrap;
        }

        .stTabs [data-baseweb="tab"] {
            height: 44px;
            border-radius: 12px 12px 0 0;
        }

        /* Mirando diretamente no texto da guia para forçar tamanho */
        button[data-baseweb="tab"] p,
        div[data-testid="stTabs"] button p {
            font-size: 1.15rem !important; /* Mantém o tamanho levemente maior */
        }

        div[data-testid="stCheckbox"] {
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid #efefef;
            margin-bottom: 6px;
            background: #ffffff;
        }

        div[data-testid="stCheckbox"]:nth-of-type(odd) {
            background: #fff8f1;
        }

        div[data-testid="stCheckbox"]:nth-of-type(even) {
            background: #ffffff;
        }

        div[data-testid="stCheckbox"] label p {
            font-weight: 700 !important;
            font-size: 1.2rem !important;
        }

        /* Oculta os ancoradores CSS que usamos para colorir os botões cirurgicamente */
        div.element-container:has(#btn-salvar-presenca),
        div.element-container:has(#btn-marcar-sim),
        div.element-container:has(#btn-marcar-nao),
        div.element-container:has(#btn-atualizar-dados),
        div.element-container:has(#btn-sortear),
        div.element-container:has(#btn-limpar),
        div.element-container:has(#btn-atualizar-presenca) {
            display: none !important;
        }

        /* Cores Cirúrgicas para aba Presença */
        div.element-container:has(#btn-atualizar-presenca) + div.element-container div.stButton > button {
            background-color: #f3f4f6 !important; border-color: #e5e7eb !important; color: #1f2937 !important;
        }
        div.element-container:has(#btn-salvar-presenca) + div.element-container div.stButton > button {
            background-color: #d1fae5 !important; border-color: #a7f3d0 !important; color: #065f46 !important;
        }
        div.element-container:has(#btn-marcar-sim) + div.element-container div.stButton > button {
            background-color: #dbeafe !important; border-color: #bfdbfe !important; color: #1e40af !important;
        }
        div.element-container:has(#btn-marcar-nao) + div.element-container div.stButton > button {
            background-color: #fee2e2 !important; border-color: #fecaca !important; color: #991b1b !important;
        }

        /* Cores Cirúrgicas para aba Sorteio */
        div.element-container:has(#btn-atualizar-dados) + div.element-container div.stButton > button {
            background-color: #f3f4f6 !important; border-color: #e5e7eb !important; color: #1f2937 !important;
        }
        div.element-container:has(#btn-sortear) + div.element-container div.stButton > button {
            background-color: #fef08a !important; border-color: #fde047 !important; color: #854d0e !important;
        }
        div.element-container:has(#btn-limpar) + div.element-container div.stButton > button {
            background-color: #ffedd5 !important; border-color: #fed7aa !important; color: #9a3412 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
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
        for col in df.columns:
            valor = row[col]
            valor = "" if pd.isna(valor) else str(valor)
            classe = "sereno-centralizado" if col in centralizar_colunas else ""
            linhas_html += f"<td class='{classe}'>{valor}</td>"
        linhas_html += "</tr>"

    return f"""
    <div class="sereno-tabela-wrapper">
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
        "PEQUENO_JOGADOR": "SIM" if categoria == "PEQUENO_JOGADOR" else "NÃO",
        "POSICAO": posicao,
    }

def descobrir_categoria_jogador(linha):
    if str(linha.get("MENSALISTA", "")).upper() == "SIM":
        return "MENSALISTA"
    if str(linha.get("DIARISTA", "")).upper() == "SIM":
        return "DIARISTA"
    if str(linha.get("CONVIDADO", "")).upper() == "SIM":
        return "CONVIDADO"
    if str(linha.get("PEQUENO_JOGADOR", "")).upper() == "SIM":
        return "PEQUENO_JOGADOR"
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
                "posicao": cadastro_map[nome]["posicao"] # Mantém a posição guardada
            })

    grupos = {
        "MENSALISTA": [],
        "DIARISTA": [],
        "CONVIDADO": [],
        "PEQUENO_JOGADOR": []
    }

    # Agrupa apenas por Categoria para o momento do sorteio (ignora a posição no sorteio)
    for jogador in presentes:
        categoria = jogador["categoria"]
        if categoria in grupos:
            grupos[categoria].append(jogador) # Passa o dicionário completo do jogador

    # Embaralha os jogadores dentro de cada categoria
    for categoria in grupos:
        random.shuffle(grupos[categoria])

    ordem_categorias = ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]

    time_1_objs = []
    time_2_objs = []

    # Distribui alternadamente (um para cada lado)
    for categoria in ordem_categorias:
        jogadores_grupo = grupos[categoria]
        if jogadores_grupo:
            distribuir_grupo_para_listas(jogadores_grupo, time_1_objs, time_2_objs)

    # Marca Titulares (primeiros 11 que entraram no time) e Reservas (12º em diante)
    for i, obj in enumerate(time_1_objs):
        obj["status"] = 1 if i < 11 else 2
    for i, obj in enumerate(time_2_objs):
        obj["status"] = 1 if i < 11 else 2

    # Função que define o peso de cada jogador para a reordenação final
    def chave_ordenacao(jogador):
        # 1º Critério: Status (1 para Titular, 2 para Reserva) - Isso garante os primeiros 11 no topo
        val_status = jogador.get("status", 2)
        
        # 2º Critério: Categoria (menor número vai pro topo dentro do seu bloco)
        ordem_cat = {"MENSALISTA": 1, "DIARISTA": 2, "CONVIDADO": 3, "PEQUENO_JOGADOR": 4}
        
        # 3º Critério: Posição
        ordem_pos = {"ZAGUEIRO": 1, "MEIO CAMPO": 2, "ATACANTE": 3}
        
        val_cat = ordem_cat.get(jogador["categoria"], 99)
        val_pos = ordem_pos.get(jogador["posicao"], 99)
        
        return (val_status, val_cat, val_pos)

    # Reordena o Time 1 e o Time 2 independentemente para exibição
    time_1_objs.sort(key=chave_ordenacao)
    time_2_objs.sort(key=chave_ordenacao)

    # Extrai apenas os nomes e remove possíveis vazios
    time_1 = [obj["nome"] for obj in time_1_objs if str(obj["nome"]).strip()]
    time_2 = [obj["nome"] for obj in time_2_objs if str(obj["nome"]).strip()]

    max_len = max(len(time_1), len(time_2))
    linhas_sorteio = []

    for i in range(max_len):
        linhas_sorteio.append({
            "ORDEM": str(i + 1),
            "Time A": time_1[i] if i < len(time_1) else "",
            "Time B": time_2[i] if i < len(time_2) else "",
        })

    return pd.DataFrame(linhas_sorteio, columns=["ORDEM", "Time A", "Time B"])

def anexar_timestamp_sorteio(df_sorteio, timestamp_str):
    df_sorteio = df_sorteio.copy()

    if df_sorteio.empty:
        return pd.DataFrame(
            [{"ORDEM": "", "Time A": "", "Time B": "", "SORTEIO": timestamp_str}],
            columns=COLUNAS_SORTEIO
        )

    df_sorteio["SORTEIO"] = ""
    df_sorteio.at[0, "SORTEIO"] = timestamp_str
    return df_sorteio[COLUNAS_SORTEIO]

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
        st.error("Nenhum jogador foi marcado como presente.")
        return

    df_sorteio = sortear_times(df_cadastro, df_presenca)
    timestamp_atual = formatar_timestamp_sorteio(agora_br())
    df_sorteio = anexar_timestamp_sorteio(df_sorteio, timestamp_atual)
    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_sorteio, COLUNAS_SORTEIO)

    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""

    st.success("Sorteio realizado com sucesso.")
    st.rerun()

def realizar_limpeza_sorteio(mapa_abas):
    ultimo_dt = obter_ultimo_timestamp_sorteio(mapa_abas)
    timestamp_str = formatar_timestamp_sorteio(ultimo_dt) if ultimo_dt else ""

    if timestamp_str:
        df_vazio = pd.DataFrame(
            [{"ORDEM": "", "Time A": "", "Time B": "", "SORTEIO": timestamp_str}],
            columns=COLUNAS_SORTEIO
        )
    else:
        df_vazio = pd.DataFrame(columns=COLUNAS_SORTEIO)

    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_vazio, COLUNAS_SORTEIO)

    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""

    st.success("Sorteio limpo com sucesso.")
    st.rerun()

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

# ==========================================================
# ESTILO
# ==========================================================
aplicar_estilo_global()

# ==========================================================
# SIDEBAR - LOGIN ADMIN
# ==========================================================
with st.sidebar:
    st.header("Acesso administrativo")

    if not st.session_state.admin_autenticado:
        with st.form("form_login_admin", clear_on_submit=True):
            usuario_admin = st.text_input("Usuário")
            senha_admin = st.text_input("Senha", type="password")
            entrar_admin = st.form_submit_button("Entrar")

        if entrar_admin:
            if usuario_admin == ADMIN_USUARIO and senha_admin == ADMIN_SENHA:
                st.session_state.admin_autenticado = True
                st.session_state.admin_erro_login = ""
                st.rerun()
            else:
                st.session_state.admin_erro_login = "Usuário ou senha inválidos."

        if st.session_state.admin_erro_login:
            st.error(st.session_state.admin_erro_login)

        st.info("Sem login, o app fica em modo visualização.")
    else:
        st.success("Login autenticado.")
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
        <p class="sereno-subtitulo">
            Sistema de cadastro, presença e sorteio de times
        </p>
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
        "PRESENCA",
        "SORTEIO"
    ])

    # ======================================================
    # ABA 1 - CADASTRO
    # ======================================================
    with abas[0]:
        df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
        df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
        df_cadastro["POSICAO"] = df_cadastro["POSICAO"].astype(str).str.strip()
        df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

        if st.session_state.admin_autenticado:
            st.markdown("### Adicionar jogador")

            with st.form("form_cadastro", clear_on_submit=True):
                nome_jogador = st.text_input("Nome do jogador")

                posicao = st.selectbox(
                    "Posição",
                    [""] + OPCOES_POSICAO,
                    format_func=formatar_opcao_vazia
                )

                categoria = st.selectbox(
                    "Categoria",
                    [""] + OPCOES_CATEGORIA,
                    format_func=formatar_opcao_vazia
                )

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
                jogador_editar = st.selectbox(
                    "Selecione o jogador",
                    nomes_existentes,
                    format_func=formatar_opcao_vazia
                )

                posicao_editar = st.selectbox(
                    "Nova posição",
                    [""] + OPCOES_POSICAO,
                    format_func=formatar_opcao_vazia
                )

                categoria_editar = st.selectbox(
                    "Nova categoria",
                    [""] + OPCOES_CATEGORIA,
                    format_func=formatar_opcao_vazia
                )

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
                        normalizar_posicao(posicao_editar)
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
                    key="excluir_jogador"
                )
                excluir = st.form_submit_button("Excluir jogador")

            if excluir:
                if not jogador_excluir:
                    st.error("Selecione o jogador para excluir.")
                else:
                    st.session_state.pendente_excluir_jogador = jogador_excluir
                    st.rerun()

            if st.session_state.pendente_excluir_jogador:
                with st.container(border=True):
                    st.warning(
                        f"Deseja realmente excluir o jogador "
                        f"'{st.session_state.pendente_excluir_jogador}'?"
                    )

                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button("Confirmar exclusão", use_container_width=True):
                            jogador_alvo = st.session_state.pendente_excluir_jogador
                            df_cadastro = df_cadastro[df_cadastro["NOME"] != jogador_alvo].reset_index(drop=True)
                            escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                            sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)

                            st.session_state.pendente_excluir_jogador = ""
                            st.success("Jogador excluído com sucesso.")
                            st.rerun()

                    with c2:
                        if st.button("Cancelar exclusão", use_container_width=True):
                            st.session_state.pendente_excluir_jogador = ""
                            st.rerun()
        else:
            st.warning("Área de edição restrita ao administrador.")

    # ======================================================
    # ABA 2 - JOGADORES CADASTRADOS
    # ======================================================
    with abas[1]:
        df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
        df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
        df_cadastro["POSICAO"] = df_cadastro["POSICAO"].astype(str).str.strip()
        df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

        # st.markdown("### Jogadores cadastrados")

        if df_cadastro.empty:
            st.info("Nenhum jogador cadastrado ainda.")
        else:
            df_exibir = df_cadastro.copy()
            df_exibir["CATEGORIA"] = df_exibir.apply(
                lambda row: descobrir_categoria_jogador(row.to_dict()), axis=1
            )
            exibir_tabela_html(df_exibir[["NOME", "CATEGORIA", "POSICAO"]])

    # ======================================================
    # ABA 3 - PRESENÇA
    # ======================================================
    with abas[2]:
        st.markdown('<div id="btn-atualizar-presenca" style="display:none;"></div>', unsafe_allow_html=True)
        if st.button("🔄 Atualizar Presenças", use_container_width=True):
            limpar_cache_planilha()
            df_fresco = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
            aplicar_df_presenca_ao_estado(df_fresco)
            st.rerun()

        df_presenca = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
        df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()
        df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

        inicializar_estado_checkboxes_presenca(df_presenca)

        if st.session_state.admin_autenticado:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown('<div id="btn-salvar-presenca" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Salvar presença", use_container_width=True):
                    novo_df_presenca = construir_df_presenca_a_partir_dos_checkboxes(df_presenca)
                    escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)
                    aplicar_df_presenca_ao_estado(novo_df_presenca)

                    st.success("Lista de presença salva com sucesso.")
                    st.rerun()

            with col2:
                st.markdown('<div id="btn-marcar-sim" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Marcar todos como SIM", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "SIM"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, True)

                    st.success("Todos os jogadores foram marcados como SIM.")
                    st.rerun()

            with col3:
                st.markdown('<div id="btn-marcar-nao" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Marcar todos como NÃO", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "NÃO"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, False)

                    st.success("Presenças zeradas com sucesso.")
                    st.rerun()

            if df_presenca.empty:
                st.info("Nenhum jogador disponível na lista de presença. Cadastre jogadores na aba CADASTRO DE JOGADORES.")
            else:
                st.markdown("<div class='sereno-card-presenca'>", unsafe_allow_html=True)
                st.markdown("<div class='sereno-secao-titulo'>Marcação de presença</div>", unsafe_allow_html=True)

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
        st.markdown('<div id="btn-atualizar-dados" style="display:none;"></div>', unsafe_allow_html=True)
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            limpar_cache_planilha()
            st.rerun()
            
        if st.session_state.admin_autenticado:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<div id="btn-sortear" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Sortear times", use_container_width=True):
                    restante = obter_segundos_restantes_bloqueio(mapa_abas)
                    if restante <= 0:
                        realizar_sorteio(mapa_abas)
                    else:
                        st.session_state.exigir_senha_master_acao = True
                        st.session_state.erro_senha_master_acao = ""
                        st.session_state.tipo_acao_pendente = "sortear"

            with col2:
                st.markdown('<div id="btn-limpar" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("Limpar sorteio", use_container_width=True):
                    restante = obter_segundos_restantes_bloqueio(mapa_abas)
                    if restante <= 0:
                        realizar_limpeza_sorteio(mapa_abas)
                    else:
                        st.session_state.exigir_senha_master_acao = True
                        st.session_state.erro_senha_master_acao = ""
                        st.session_state.tipo_acao_pendente = "limpar"

            if st.session_state.exigir_senha_master_acao:
                restante = obter_segundos_restantes_bloqueio(mapa_abas)
                acao_txt = "novo sorteio" if st.session_state.tipo_acao_pendente == "sortear" else "limpar sorteio"

                st.warning(
                    f"Essa ação só pode ser feita sem senha após 10 minutos. "
                    f"Tempo restante: {formatar_tempo_restante(restante)}. "
                    f"Digite a senha master para autorizar {acao_txt} agora."
                )

                with st.container(border=True):
                    senha_master_digitada = st.text_input(
                        "Senha master",
                        type="password",
                        key="senha_master_acao_widget"
                    )

                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button("Autorizar", use_container_width=True):
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
                        if st.button("Cancelar", use_container_width=True):
                            st.session_state.exigir_senha_master_acao = False
                            st.session_state.erro_senha_master_acao = ""
                            st.session_state.tipo_acao_pendente = ""
                            st.rerun()

                    if st.session_state.erro_senha_master_acao:
                        st.error(st.session_state.erro_senha_master_acao)

        else:
            st.warning("Sortear e limpar sorteio são ações restritas ao administrador.")

        df_sorteio = ler_aba_com_cabecalho(mapa_abas, ABA_SORTEIO, COLUNAS_SORTEIO)
        df_sorteio["ORDEM"] = df_sorteio["ORDEM"].astype(str).str.strip()
        df_sorteio = df_sorteio[df_sorteio["ORDEM"] != ""].reset_index(drop=True)

        if df_sorteio.empty:
            st.info("Ainda não há sorteio realizado.")
        else:
            st.markdown("### Resultado do sorteio")
            exibir_tabela_html(df_sorteio[["ORDEM", "Time A", "Time B"]], centralizar_colunas=["ORDEM", "Time A", "Time B"])

    # ======================================================
    # LOGO NO FINAL DA PÁGINA
    # ======================================================
    col_logo_esq, col_logo_centro, col_logo_dir = st.columns([1, 1.5, 1])
    with col_logo_centro:
        logo_path = Path("SERENO FC.png")
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)

except SpreadsheetNotFound:
    st.error("Planilha 'FUTEBOL_SERENO' não encontrada ou não compartilhada com a service account.")
except Exception as e:
    st.error("Erro ao executar a aplicação.")
    st.exception(e)
