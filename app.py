import random
import time
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
COLUNAS_SORTEIO = ["ORDEM", "TIME_1", "TIME_2"]

OPCOES_POSICAO = ["ZAGUEIRO", "MEIO CAMPO", "ATACANTE"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================================================
# ACESSO ADMINISTRADOR
# ==========================================================
ADMIN_USUARIO = "Administrador"
ADMIN_SENHA = "Administrador@123"

# ==========================================================
# CONTROLE DE NOVO SORTEIO / LIMPAR SORTEIO
# ==========================================================
TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS = 10 * 60
SENHA_MASTER_SORTEIO = "123"

# ==========================================================
# UTILITÁRIOS DE RESILIÊNCIA
# ==========================================================
def executar_com_retry(func, *args, **kwargs):
    tentativas = 5
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
    conectar_gsheet.clear()

# ==========================================================
# FUNÇÕES DE LEITURA/ESCRITA
# ==========================================================
def ler_aba_com_cabecalho(mapa_abas, nome_aba, colunas_esperadas):
    ws = obter_worksheet(mapa_abas, nome_aba)
    valores = executar_com_retry(ws.get_all_values)

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

# ==========================================================
# FUNÇÕES DE NEGÓCIO
# ==========================================================
def normalizar_nome(nome):
    return str(nome).strip()

def normalizar_posicao(posicao):
    p = str(posicao).strip().upper()
    return p if p in OPCOES_POSICAO else ""

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
        "MENSALISTA": {"ZAGUEIRO": [], "MEIO CAMPO": [], "ATACANTE": []},
        "DIARISTA": {"ZAGUEIRO": [], "MEIO CAMPO": [], "ATACANTE": []},
        "CONVIDADO": {"ZAGUEIRO": [], "MEIO CAMPO": [], "ATACANTE": []},
        "PEQUENO_JOGADOR": {"ZAGUEIRO": [], "MEIO CAMPO": [], "ATACANTE": []},
    }

    for jogador in presentes:
        categoria = jogador["categoria"]
        posicao = jogador["posicao"]
        if categoria in grupos and posicao in grupos[categoria]:
            grupos[categoria][posicao].append(jogador["nome"])

    for categoria in grupos:
        for posicao in grupos[categoria]:
            random.shuffle(grupos[categoria][posicao])

    time_1 = []
    time_2 = []
    proximo_time = 1

    def adicionar_jogador(nome_jogador):
        nonlocal proximo_time, time_1, time_2

        if len(time_1) < len(time_2):
            time_1.append(nome_jogador)
            proximo_time = 2
        elif len(time_2) < len(time_1):
            time_2.append(nome_jogador)
            proximo_time = 1
        else:
            if proximo_time == 1:
                time_1.append(nome_jogador)
                proximo_time = 2
            else:
                time_2.append(nome_jogador)
                proximo_time = 1

    ordem_categorias = ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]
    ordem_posicoes = ["ZAGUEIRO", "MEIO CAMPO", "ATACANTE"]

    for categoria in ordem_categorias:
        for posicao in ordem_posicoes:
            for nome_jogador in grupos[categoria][posicao]:
                adicionar_jogador(nome_jogador)

    max_len = max(len(time_1), len(time_2), 0)
    linhas_sorteio = []

    for i in range(max_len):
        linhas_sorteio.append({
            "ORDEM": str(i + 1),
            "TIME_1": time_1[i] if i < len(time_1) else "",
            "TIME_2": time_2[i] if i < len(time_2) else "",
        })

    df_sorteio = pd.DataFrame(linhas_sorteio, columns=COLUNAS_SORTEIO)
    return df_sorteio

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
    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_sorteio, COLUNAS_SORTEIO)

    st.session_state.ultimo_sorteio_ts = time.time()
    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""

    limpar_cache_planilha()
    st.success("Sorteio realizado com sucesso.")
    st.rerun()

def realizar_limpeza_sorteio(mapa_abas):
    df_vazio = pd.DataFrame(columns=COLUNAS_SORTEIO)
    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_vazio, COLUNAS_SORTEIO)

    st.session_state.exigir_senha_master_acao = False
    st.session_state.erro_senha_master_acao = ""
    st.session_state.tipo_acao_pendente = ""

    limpar_cache_planilha()
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

if "ultimo_sorteio_ts" not in st.session_state:
    st.session_state.ultimo_sorteio_ts = None

if "exigir_senha_master_acao" not in st.session_state:
    st.session_state.exigir_senha_master_acao = False

if "erro_senha_master_acao" not in st.session_state:
    st.session_state.erro_senha_master_acao = ""

if "tipo_acao_pendente" not in st.session_state:
    st.session_state.tipo_acao_pendente = ""

# ==========================================================
# SIDEBAR - LOGIN ADMIN
# ==========================================================
with st.sidebar:
    st.header("Acesso administrativo")

    if not st.session_state.admin_autenticado:
        with st.form("form_login_admin"):
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

        st.info("Sem login de administrador, o app ficará apenas em modo de visualização.")
    else:
        st.success("Administrador autenticado.")
        st.write(f"Usuário: {ADMIN_USUARIO}")

        if st.button("Sair do modo administrador", use_container_width=True):
            st.session_state.admin_autenticado = False
            st.session_state.admin_erro_login = ""
            st.rerun()

# ==========================================================
# APP
# ==========================================================
st.title("Sereno F.C.")

try:
    planilha, mapa_abas = conectar_gsheet()

    if not st.session_state.abas_inicializadas:
        inicializar_abas_se_necessario(mapa_abas)
        st.session_state.abas_inicializadas = True

    if st.session_state.admin_autenticado:
        st.success("Modo administrador ativo.")
    else:
        st.info("Modo visualização ativo. Faça login na barra lateral para alterar dados.")

    abas = st.tabs(["CADASTRO DE JOGADORES", "LISTA DE PRESENCA", "SORTEIO DOS TIMES"])

    with abas[0]:
        st.subheader("Cadastro de jogadores")

        df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
        df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
        df_cadastro["POSICAO"] = df_cadastro["POSICAO"].astype(str).str.strip()
        df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

        if st.session_state.admin_autenticado:
            st.markdown("### Adicionar novo jogador")
            with st.form("form_cadastro"):
                nome_jogador = st.text_input("Nome do jogador")
                categoria = st.radio(
                    "Categoria",
                    ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"],
                    horizontal=True
                )
                posicao = st.selectbox("Posição", OPCOES_POSICAO)
                enviar_cadastro = st.form_submit_button("Salvar jogador")

            if enviar_cadastro:
                nome_jogador = normalizar_nome(nome_jogador)
                posicao = normalizar_posicao(posicao)

                if not nome_jogador:
                    st.error("Informe o nome do jogador.")
                elif nome_jogador.upper() in [x.upper() for x in df_cadastro["NOME"].tolist()]:
                    st.error("Esse jogador já está cadastrado.")
                else:
                    nova_linha = montar_linha_cadastro(nome_jogador, categoria, posicao)
                    df_cadastro = pd.concat([df_cadastro, pd.DataFrame([nova_linha])], ignore_index=True)

                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)

                    limpar_cache_planilha()
                    st.success("Jogador cadastrado com sucesso.")
                    st.rerun()
        else:
            st.warning("Área de edição restrita ao administrador.")

        st.markdown("---")
        st.markdown("### Jogadores cadastrados")

        if df_cadastro.empty:
            st.info("Nenhum jogador cadastrado ainda.")
        else:
            df_exibir = df_cadastro.copy()
            df_exibir["CATEGORIA"] = df_exibir.apply(
                lambda row: descobrir_categoria_jogador(row.to_dict()), axis=1
            )
            st.dataframe(df_exibir[["NOME", "CATEGORIA", "POSICAO"]], use_container_width=True, hide_index=True)

            if st.session_state.admin_autenticado:
                st.markdown("### Atualizar jogador")
                nomes_existentes = df_cadastro["NOME"].tolist()

                with st.form("form_editar"):
                    jogador_editar = st.selectbox("Selecione o jogador", nomes_existentes)
                    linha_jogador = df_cadastro[df_cadastro["NOME"] == jogador_editar].iloc[0].to_dict()

                    categoria_atual = descobrir_categoria_jogador(linha_jogador)
                    posicao_atual = normalizar_posicao(linha_jogador.get("POSICAO", ""))

                    opcoes_categoria = ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]
                    indice_categoria = opcoes_categoria.index(categoria_atual) if categoria_atual in opcoes_categoria else 0
                    indice_posicao = OPCOES_POSICAO.index(posicao_atual) if posicao_atual in OPCOES_POSICAO else 0

                    categoria_editar = st.radio(
                        "Nova categoria",
                        opcoes_categoria,
                        index=indice_categoria,
                        horizontal=True
                    )
                    posicao_editar = st.selectbox("Nova posição", OPCOES_POSICAO, index=indice_posicao)
                    salvar_edicao = st.form_submit_button("Atualizar jogador")

                if salvar_edicao:
                    idx = df_cadastro.index[df_cadastro["NOME"] == jogador_editar][0]
                    linha_atualizada = montar_linha_cadastro(jogador_editar, categoria_editar, normalizar_posicao(posicao_editar))
                    for col in COLUNAS_CADASTRO:
                        df_cadastro.at[idx, col] = linha_atualizada[col]

                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)

                    limpar_cache_planilha()
                    st.success("Jogador atualizado com sucesso.")
                    st.rerun()

                st.markdown("### Excluir jogador")
                with st.form("form_excluir"):
                    jogador_excluir = st.selectbox(
                        "Selecione o jogador para excluir",
                        nomes_existentes,
                        key="excluir_jogador"
                    )
                    excluir = st.form_submit_button("Excluir jogador")

                if excluir:
                    df_cadastro = df_cadastro[df_cadastro["NOME"] != jogador_excluir].reset_index(drop=True)
                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)

                    limpar_cache_planilha()
                    st.success("Jogador excluído com sucesso.")
                    st.rerun()

    with abas[1]:
        st.subheader("Lista de presença")

        df_presenca = sincronizar_lista_presenca(mapa_abas, forcar_gravacao=False)
        df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()
        df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

        inicializar_estado_checkboxes_presenca(df_presenca)

        if st.session_state.admin_autenticado:
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Salvar presença", use_container_width=True):
                    novo_df_presenca = construir_df_presenca_a_partir_dos_checkboxes(df_presenca)
                    escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)
                    aplicar_df_presenca_ao_estado(novo_df_presenca)

                    limpar_cache_planilha()
                    st.success("Lista de presença salva com sucesso.")
                    st.rerun()

            with col2:
                if st.button("Marcar todos como SIM", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "SIM"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, True)

                    limpar_cache_planilha()
                    st.success("Todos os jogadores foram marcados como SIM.")
                    st.rerun()

            with col3:
                if st.button("Marcar todos como NÃO", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "NÃO"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)
                        forcar_estado_checkboxes_presenca(df_presenca, False)

                    limpar_cache_planilha()
                    st.success("Presenças zeradas com sucesso.")
                    st.rerun()

            if df_presenca.empty:
                st.info("Nenhum jogador disponível na lista de presença. Cadastre jogadores na aba CADASTRO DE JOGADORES.")
            else:
                st.markdown("### Marcação de presença")
                for _, row in df_presenca.iterrows():
                    nome = normalizar_nome(row["NOME"])
                    st.checkbox(nome, key=chave_checkbox_presenca(nome))
        else:
            st.warning("Alterações de presença restritas ao administrador.")

        st.markdown("### Presenças atuais")
        if df_presenca.empty:
            st.info("Nenhum jogador disponível na lista de presença.")
        else:
            st.dataframe(df_presenca, use_container_width=True, hide_index=True)

    with abas[2]:
        st.subheader("Sorteio dos times")

        if st.session_state.admin_autenticado:
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Sortear times", use_container_width=True):
                    agora = time.time()
                    ultimo_sorteio_ts = st.session_state.ultimo_sorteio_ts

                    if ultimo_sorteio_ts is None or (agora - ultimo_sorteio_ts) >= TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS:
                        realizar_sorteio(mapa_abas)
                    else:
                        st.session_state.exigir_senha_master_acao = True
                        st.session_state.erro_senha_master_acao = ""
                        st.session_state.tipo_acao_pendente = "sortear"

            with col2:
                if st.button("Limpar sorteio", use_container_width=True):
                    agora = time.time()
                    ultimo_sorteio_ts = st.session_state.ultimo_sorteio_ts

                    if ultimo_sorteio_ts is None or (agora - ultimo_sorteio_ts) >= TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS:
                        realizar_limpeza_sorteio(mapa_abas)
                    else:
                        st.session_state.exigir_senha_master_acao = True
                        st.session_state.erro_senha_master_acao = ""
                        st.session_state.tipo_acao_pendente = "limpar"

            if st.session_state.exigir_senha_master_acao:
                agora = time.time()
                ultimo_sorteio_ts = st.session_state.ultimo_sorteio_ts or 0
                restante = max(0, TEMPO_BLOQUEIO_SORTEIO_SEGUNDOS - (agora - ultimo_sorteio_ts))

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
                        if st.button("Autorizar ação", use_container_width=True):
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
                        if st.button("Cancelar autorização", use_container_width=True):
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
            st.dataframe(df_sorteio, use_container_width=True, hide_index=True)

            qtd_time_1 = (df_sorteio["TIME_1"].astype(str).str.strip() != "").sum()
            qtd_time_2 = (df_sorteio["TIME_2"].astype(str).str.strip() != "").sum()

            c1, c2 = st.columns(2)
            c1.metric("Jogadores no TIME_1", int(qtd_time_1))
            c2.metric("Jogadores no TIME_2", int(qtd_time_2))

except SpreadsheetNotFound:
    st.error("Planilha 'FUTEBOL_SERENO' não encontrada ou não compartilhada com a service account.")
except Exception as e:
    st.error("Erro ao executar a aplicação.")
    st.exception(e)
