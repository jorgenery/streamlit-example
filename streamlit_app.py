import streamlit as st
from googlesearch import search
from bingsearchpy import engine as bing_search
from openpyxl import Workbook
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.corpus import wordnet
from unidecode import unidecode
# from gensim.summarization import summarize
import socket as s 
import pandas as pd
import spacy
import re
import base64
import time 
import os
# Pega GeoReferenciamento Site
def get_geo_referenci(url):
    parsed_url = urlparse(url)
    host = parsed_url.netloc
    ip = s.gethostbyname(host) 
    url = f"http://ipinfo.io/{ip}/json"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36"}
    response = requests.get(url, headers=headers)
    return response.json()

# Função para pesquisar no Bing
def search_bing(query, num_results):
    first = 1
    num = 0
    urls = list()
    while (num < num_results):
        url = f"https://www.bing.com/search?q={query}&first={first}&FORM=PERE"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36"}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")
            search_results = soup.find_all("a",attrs={'h': True,'data-pturl':False, 'href': lambda href: href.startswith('http')})
            list_urls = list(set([a_element.get('href') for a_element in search_results]))
            urls = urls + list_urls
            num = num + len(list_urls)
            first = first + 10
        except:
            pass
    return urls[0:num_results]

# Função para limpar o conteúdo da página
def clean_text(text):
    article_text = text
    article_text = re.sub(r'\\[[0-9]*\\]', ' ',article_text)
    article_text = re.sub('[^a-zA-Z.,]', ' ',article_text)
    article_text = re.sub(r"\b[a-zA-Z]\b",'',article_text)
    article_text = re.sub("[A-Z]\Z",'',article_text)
    article_text = re.sub(r'\s+', ' ', article_text)
    return article_text

# Função para extrair o conteúdo da página
def extract_content(url):
    try:
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")    
        content = soup.get_text()
    except:
        content = ''
    return clean_text(unidecode(content))
# Carrega Modelos
@st.cache_resource
def load_models():    
    global nlp
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')
    try:                        
        if 'nlp' not in st.session_state:
            st.session_state.nlp = spacy.load('en_core_web_sm')
    except OSError:
        print('Downloading language model for the spaCy POS tagger\n'
            "(don't worry, this will only happen once)")
        from spacy.cli import download
        download('en_core_web_sm')
        if 'nlp' not in st.session_state:
            st.session_state.nlp = spacy.load('en_core_web_sm')
# Cria Link para Download de Dados    
def make_downloadable_df(data):
    csvfile = data.to_csv(index=False)
    b64 = base64.b64encode(csvfile.encode()).decode()  # B64 encoding
    st.markdown("### ** Download CSV File ** ")
    new_filename = "resultado.csv"
    href = f'<a href="data:file/csv;base64,{b64}" download="{new_filename}">Download</a>'
    st.markdown(href, unsafe_allow_html=True)
# Pincipal
def main():
    # Configuração do título e descrição da página    
    nameresult = 'resultado_' +time.strftime("%H%M%S", time.gmtime())+'.xlsx'
    if 'nameresult' not in st.session_state:
        st.session_state.nameresult = nameresult
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame([], columns=['site', 'resumo', 'links relacionados', 'sinonimos','relevância','entidades'])
    global visited_sites
    visited_sites = list()
    global selected_sites
    selected_sites = list()
    global search_sites 
    search_sites = list()
    # Menu de Opções
    menu = ["Home","Looking","Analytic","About"]
    choice = st.sidebar.selectbox("Menu", menu)
    if choice == "Home":
        about()
    elif choice == "Looking":
        looking()
    elif choice == "Analytic":
        analytics()
    elif choice == "About":
        about()  
# Sobre o APP
def about():
    st.subheader("About")
    st.markdown("### Instituto de Computação – Universidade Federal da Bahia (UFBA)")    
    st.markdown("* Prototipo: Automação de Pesquisa em literatura cinza")
    st.markdown("* Professor: Dr. Manoel Mendonça")
    st.markdown("O objetivo é facilitar a busca e analise. Porem a ferramenta é um prototipo com algumas funcionalidades.")
    st.success("Autor : Jorge Nery <jorge.nery@ufba.br>")    
    st.subheader("Pontos em Aberto:")
    # st.info("Implemantar busca no BING",icon="❌")
    # st.info("Implemantar analise de sinônimos",icon="❌")
    # st.info("Implemantar analise de sublinks",icon="❌")
    st.info("Avaliar calculo de Score Relevância",icon="❌")       
    st.warning("Avaliar eficiência", icon="⚠️")

def analytics():
    st.subheader("Analytics")
    # Exibe os resultados na tabela
    namesesult = st.session_state.nameresult
    st.subheader("Resultados {}".format(namesesult))
    if os.path.exists(namesesult):
        df = pd.read_excel(namesesult)
    else:
        df = st.session_state.df
    st.dataframe(df)
    # Botões de download
    make_downloadable_df(df)
    
# Calcula Score por ocorrencia da keyword ou Similaridade
def score_analyzer(text, links, questions, keywords):
    # Calcula a relevância semântica para cada link relacionado
    # nlp = spacy.load('en_core_web_sm')
    nlp = st.session_state.nlp
    relevance_scores = []    
    relevance_score = 0
    regenerative_ai_scores = []
    link_doc = nlp(text)
    if len(questions) > 0:
        relevance_score = sum([link_doc.similarity(nlp(question)) for question in questions]) / len(questions)
        relevance_scores.append(relevance_score)    
    keyword_match = any(re.search(fr'\b{keyword}\b', text, flags=re.IGNORECASE) for keyword in keywords.split(','))
    regenerative_ai_scores.append(keyword_match)    
    search_sublinks = st.session_state.search_sublinks                
    if search_sublinks:
        for link in links.split(','):
            link_text = extract_content(link)
            link_doc = nlp(link_text)
            if len(questions) > 0:
                relevance_score = sum([link_doc.similarity(nlp(question)) for question in questions]) / len(questions)
                relevance_scores.append(relevance_score)    
            keyword_match = any(re.search(fr'\b{keyword}\b', link_text, flags=re.IGNORECASE) for keyword in keywords.split(','))
            regenerative_ai_scores.append(keyword_match)            
    
    regenerative_score = sum(regenerative_ai_scores) / len(regenerative_ai_scores)   
    relevance_score = sum(relevance_scores)/len(relevance_scores)    
    return (relevance_score, regenerative_score)
# Pega os SubLinks da Pagina
def sub_links(soup, base_url):
    # Extrai links relacionados da página    
    sub_urls = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href is None or href.startswith('#'):
            continue
        full_url = urljoin(base_url, href)
        if urlparse(full_url).netloc == urlparse(base_url).netloc:
            if full_url not in visited_sites:
                visited_sites.append(full_url)
                sub_urls.append(full_url)
    links_str = ','.join(sub_urls)
    return links_str
# Cria lista de Sinônimos
def synonym_analyzer(keywords):
    # Pesquisa de sinônimos
    search_synonyms = st.session_state.search_synonyms
    synonyms_str = ''    
    synonyms = set()
    for keyword in keywords.split(','):
        synonyms.add(keyword)        
        if search_synonyms:
            synsets = wordnet.synsets(keyword)
            for synset in synsets:
                for lemma in synset.lemmas():
                    synonyms.add(lemma.name())
    synonyms_str = ','.join(synonyms)
    return synonyms_str
# Gera Sumario pela Tecnica PorterStemmer    
def summary_analyzer(text):
    # Inicializa o stemmer   
    stemmer = PorterStemmer()    
    # Tokeniza o texto em frases
    sentences = sent_tokenize(text)
    # Remove stopwords e aplica o stemmer às palavras
    stop_words = set(stopwords.words('english'))  # Altere para o idioma desejado
    stemmed_sentences = []                        
    for sentence in sentences:
        words = sentence.split()
        stemmed_words = [stemmer.stem(word) for word in words if word.lower() not in stop_words]
        stemmed_sentence = ' '.join(stemmed_words)
        stemmed_sentences.append(stemmed_sentence)
    # Combina as frases em um único resumo
    summary = ' '.join(stemmed_sentences[:2])  # Altere o número de frases desejado
    return summary
# Cria Lista de Entidades
def entity_analyzer(my_text):    
    nlp = st.session_state.nlp
    docx = nlp(my_text)   
    entities = [entity.text for entity in docx.ents]
    entities_str = ','.join(entities)
    return entities_str   
# Efatua a analise do Link
def url_analyzer(df, url, keywords, questions, relevant_keywords):    
    try:
        page_content = requests.get(url,timeout=30).text    
        soup = BeautifulSoup(page_content, 'html.parser')
        # Verifica se todas as palavras-chave estão presentes na página
        if all(keyword in page_content for keyword in keywords.split(',')):
            # Extrai o texto da página                
            text = clean_text(soup.get_text())
            links_str = sub_links(soup, url)                                        
            synonyms_str = synonym_analyzer(relevant_keywords)        
            summary = summary_analyzer(text)
            score = score_analyzer(text, links_str, questions, synonyms_str)     
            entitys = entity_analyzer(text)                                               
            reg = [url, summary, links_str, synonyms_str, score, entitys]                   
            df = pd.concat([df, pd.DataFrame([reg], columns=df.columns)], ignore_index=True)                                                  
            with tab_found:
                with st.expander(f'{url} - ( {score} )'):
                    st.write(f'{summary}')
                    st.write(f'{entitys}  - {synonyms_str}')
                    st.write(f'{links_str}')
        else:        
            with tab_nfound:
                with st.expander(f'{url}'):
                    st.write(f'{keywords}')
    except:
        with tab_nfound:
            with st.expander(f'{url} - Timeout'):
                st.write(f'Indisponível')
    return df
def looking():
    # Cria dataframe        
    df = st.session_state.df        
    # Título da aplicação
    st.title("Looking Helpfull")
     # Escolha do mecanismo de busca     
    search_engine = st.sidebar.selectbox("Selecione o mecanismo de busca", ("Google", "Bing"))
    # Número máximo de resultados
    if 'num_results' not in st.session_state:
        st.session_state.num_results = 10
    num_results = st.sidebar.slider("Número máximo de resultados", min_value=1, max_value=1000, value=st.session_state.num_results)
    if num_results != st.session_state.num_results:
        st.session_state.num_results = num_results
    # Pesquisa de sinônimos
    global search_synonyms    
    if 'search_synonyms' not in st.session_state:
        st.session_state.search_synonyms = False
    search_synonyms = st.session_state.search_synonyms
    search_synonyms = st.sidebar.checkbox("Pesquisar sinônimos", value=search_synonyms, key='search_synonyms')
    # Pesquisa SubLinks
    global search_sublinks
    if 'search_sublinks' not in st.session_state:
        st.session_state.search_sublinks = False
    search_sublinks = st.session_state.search_sublinks    
    search_sublinks = st.sidebar.checkbox("Pesquisar SubLinks", value=search_sublinks, key='search_sublinks')
    # Termo de pesquisa
    query = st.text_input("Digite o termo de pesquisa Ex: deadline AND process AND orcanos")
    # Palavras-chave obrigatorias serem verificadas
    keywords = st.text_input("Palavras-chave separadas por vírgula Ex: deadline,process")
    # Palavras-chave a serem verificadas para relevância
    relevant_keywords = st.text_input("Palavras-relevantes separadas por vírgula Ex: deadline,process,orcanos")
    #  Frases a serem verificadas semanticamente 
    str_questions = st.text_input("Frases para avaliar a relevância semântica separadas por vírgula Ex: deadline,process,orcanos")        
    # Carrega o modelo de linguagem do spaCy
    # nlp = st.session_state.nlp
    # Botão para iniciar a pesquisa
    if st.button("Pesquisar"):
        placeholder = st.empty()
        global tab_found
        global tab_nfound
        tab_found, tab_nfound = st.tabs(["Selecionados", "Não Selecionados"])
        questions = str_questions.split(',')
        # Realiza a pesquisa e itera pelos resultados
        selected_sites = []        
        search_sites = []
        entidades_str =''
        summary = ''
        links_str = ''
        synonyms_str = ''
        relevance_scores = []
        score = 0
        if search_engine == "Google":
            search_function = search
        else:
            search_function = search_bing        
        with placeholder.container():
            my_bar = st.progress(0,text="Aguarde Processando...")
        num = 0        
        for result in search_function(query, num_results=num_results):
            # Faz o download do conteúdo da página  
            percent_complete = (num / num_results)
            if percent_complete>1:
                percent_complete = 1.0          
            with placeholder.container():
                my_bar = st.progress(percent_complete,text="Processando..({})".format(result))
            if result not in visited_sites:
                visited_sites.append(result)                
                #try:
                df = url_analyzer(df, result, keywords, questions, relevant_keywords)
                #except:
                #    pass            
            num = num + 1            
        # Salva a planilha com Resultados
        namesesult = st.session_state.nameresult
        df.to_excel(namesesult, index=False)        
        with placeholder.container():
            st.success("Concluido")
            st.balloons()

if __name__ == '__main__':
    st.set_page_config(page_title="Looking Helpfull", page_icon=":memo:", layout="wide")    
    load_models()
    main()
