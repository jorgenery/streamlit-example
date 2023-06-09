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
import pandas as pd
import spacy
import re
import base64
import time 

def clean_text(text):
    article_text = text
    article_text = re.sub(r'\\[[0-9]*\\]', ' ',article_text)
    article_text = re.sub('[^a-zA-Z.,]', ' ',article_text)
    article_text = re.sub(r"\b[a-zA-Z]\b",'',article_text)
    article_text = re.sub("[A-Z]\Z",'',article_text)
    article_text = re.sub(r'\s+', ' ', article_text)
    return article_text
@st.cache_resource
def load_models():    
    global nlp
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')
    try:
        nlp = spacy.load('en_core_web_sm')
    except OSError:
        print('Downloading language model for the spaCy POS tagger\n'
            "(don't worry, this will only happen once)")
        from spacy.cli import download
        download('en_core_web_sm')
        nlp = spacy.load('en_core_web_sm')
    
def make_downloadable_df(data):
    csvfile = data.to_csv(index=False)
    b64 = base64.b64encode(csvfile.encode()).decode()  # B64 encoding
    st.markdown("### ** Download CSV File ** ")
    new_filename = "resultado.csv"
    href = f'<a href="data:file/csv;base64,{b64}" download="{new_filename}">Download</a>'
    st.markdown(href, unsafe_allow_html=True)

def main():
    # Configuração do título e descrição da página    
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
        df = looking()
    elif choice == "Analytic":
        analytics()
    elif choice == "About":
        about()  

def about():
    st.subheader("About")
    st.markdown("### Instituto de Computação – Universidade Federal da Bahia (UFBA)")    
    st.markdown("* Prototipo: Automação de Pesquisa em literatura cinza")
    st.markdown("* Professor: Dr. Manoel Mendonça")
    st.markdown("O objetivo é facilitar a busca e analise. Porem a ferramenta é um prototipo com algumas funcionalidades.")
    st.success("Autor : Jorge Nery <jorge.nery@ufba.br>")    
    st.subheader("Pontos em Aberto:")
    st.info("Implemantar busca no BING",icon="❌")
    st.info("Implemantar analise de sinônimos",icon="❌")
    st.info("Implemantar analise de sublinks",icon="❌")
    st.info("Avaliar calculo de Score Relevância",icon="❌")       
    st.warning("Avaliar eficiência", icon="⚠️")

def analytics():
    st.subheader("Analytics")
    # Exibe os resultados na tabela
    st.subheader("Resultados")
    df = pd.read_excel("resultados.xlsx")
    st.dataframe(df)
    # Botões de download
    make_downloadable_df(df)
    if selected_sites:
        selected_df = df[df.isin(selected_sites)]
        make_downloadable_df(selected_df)

def score_analyzer(questions, links):
    # Calcula a relevância semântica para cada link relacionado
    relevance_scores = []
    regenerative_ai_scores = []
    for link in links:
        link_content = requests.get(link).text
        link_text = BeautifulSoup(link_content, 'html.parser').get_text()
        link_doc = nlp(link_text)
        relevance_score = sum([link_doc.similarity(nlp(question)) for question in questions]) / len(questions)
        relevance_scores.append(relevance_score)    
        # Avaliação de IA Regenerativa
        keyword_match = any(re.search(fr'\b{keyword}\b', link_text, flags=re.IGNORECASE) for keyword in keywords)
        regenerative_ai_scores.append(keyword_match)

    # Adiciona a avaliação de IA Regenerativa na coluna F
    if regenerative_ai_scores:
        regenerative_ai_score = any(regenerative_ai_scores)
        score = regenerative_ai_score
    else:
        score = any(relevance_scores)
    return score

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
    links_str = ', '.join(sub_urls)
    return links_str
@st.cache_data
def synonym_analyzer(keywords):
    # Pesquisa de sinônimos
    synonyms_str = ''
    if search_synonyms:
        synonyms = set()
        for keyword in keywords.split(','):
            synsets = wordnet.synsets(keyword)
            for synset in synsets:
                for lemma in synset.lemmas():
                    synonyms.add(lemma.name())
        synonyms_str = ', '.join(synonyms)
    return synonyms_str
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

def entity_analyzer(my_text):
    nlp = spacy.blank("en")
    docx = nlp(my_text)    
    entities = [(entity.text,entity.label_)for entity in docx.ents]
    entities_str = ', '.join(entities)
    return entities_str    

def url_analyzer(df, url, keywords, questions):    
    page_content = requests.get(url).text
    soup = BeautifulSoup(page_content, 'html.parser')
    links_str = sub_links(soup, url)                                    
    synonyms_str = synonym_analyzer(keywords)        
    # Verifica se todas as palavras-chave estão presentes na página
    if all(keyword in page_content for keyword in keywords.split(',')):
        # Extrai o texto da página                
        text = soup.get_text()
        summary = summary_analyzer(text)
        score = score_analyzer(questions, synonyms_str)     
        entitys = entity_analyzer(text)                                               
        reg = [url, summary, links_str, synonyms_str, score, entitys]                   
        df = pd.concat([df, pd.DataFrame([reg], columns=df.columns)], ignore_index=True)                                                  
        with tab_found:
            with st.expander(f'{url} - ( {score} )'):
                st.write(f'{summary}')
                st.write(f'{entitys}  - {synonyms_str}')
                st.write(f'{links_str}')
        # Todo: Implementar analise sub links
        #    for sub_url in links_str.split(','):                
        #        df=url_analyzer(df, sub_url, keywords, questions)            
    else:        
        with tab_nfound:
            with st.expander(f'{url}'):
                st.write(f'{links_str} - {synonyms_str}')
        #for sub_url in links_str.split(','):
        #    with st.expander(sub_url):
        #        df=url_analyzer(df, sub_url, keywords, questions)                                    
    return df
def looking():
    st.subheader("Looking Helpfull")    
    df = pd.DataFrame([], columns=['site', 'resumo', 'links relacionados', 'sinonimos','relevância','entidades'])
    # Título da aplicação
    st.title("Looking Helpfull")
     # Escolha do mecanismo de busca     
    search_engine = st.sidebar.selectbox("Selecione o mecanismo de busca", ("Google", "Bing"))
    # Número máximo de resultados
    num_results = st.sidebar.slider("Número máximo de resultados", min_value=1, max_value=1000, value=10)
    # Pesquisa de sinônimos
    global search_synonyms
    search_synonyms = st.sidebar.checkbox("Pesquisar sinônimos")
    # Pesquisa SubLinks
    search_sublinks = st.sidebar.checkbox("Pesquisar SubLinks")
    # Termo de pesquisa
    query = st.text_input("Digite o termo de pesquisa Ex: deadline AND process AND orcanos")
    # Palavras-chave a serem verificadas
    keywords = st.text_input("Palavras-chave separadas por vírgula Ex: deadline, process, orcanos")
    # Palavras-chave a serem verificadas
    str_questions = st.text_input("Perguntas para avaliar a relevância semântica separadas por vírgula Ex: deadline, process, orcanos")        
    # Carrega o modelo de linguagem do spaCy
    nlp = spacy.load("en_core_web_sm")
    # Botão para iniciar a pesquisa
    if st.button("Pesquisar"):
        placeholder = st.empty()
        global tab_found
        global tab_nfound
        tab_found, tab_nfound = st.tabs(["Selecionados", "Não Selecionados"])
        questions = str_questions.split(',')
        # Realiza a pesquisa e itera pelos resultados
        row = 1  # Inicia na segunda linha da planilha
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
            search_function = bing_search.search
        with placeholder.container():
            st.warning("Aguarde Processando...")
        for result in search_function(query, num_results=num_results):
            # Faz o download do conteúdo da página            
            if result not in visited_sites:
                visited_sites.append(result)                
                df = url_analyzer(df, result, keywords, questions)                
        # Salva a planilha
        df.to_excel("resultados.xlsx", index=False)
        with placeholder.container():
            st.success("Concluido")
    return df
if __name__ == '__main__':
    st.set_page_config(page_title="Looking Helpfull", page_icon=":memo:", layout="wide")    
    load_models()
    main()