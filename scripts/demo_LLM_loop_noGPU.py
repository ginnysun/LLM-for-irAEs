## Please cite: Sun, V. H., Heemelaar, J. C., Hadzic, I., Raghu, V. K., Wu, C. Y., 
## Zubiri, L., ... & Reynolds, K. L. (2024). Enhancing Precision in Detecting Severe 
## Immune-Related Adverse Events: Comparative Analysis of Large Language Models and 
## International Classification of Disease Codes in Patient Records. Journal of Clinical 
## Oncology, JCO-24.

## Code written by Virginia Sun, MD

# Import packages
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_community.llms import Ollama
import pyreadr
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import LlamaCppEmbeddings
from langchain.chains import LLMChain
from langchain_community.llms import LlamaCpp
from langchain.chains import RetrievalQA
from langchain.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain import hub
import numpy as np
import pandas as pd
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables import RunnableParallel
from langchain.prompts import ChatPromptTemplate
from langchain.prompts import PromptTemplate
from langchain.prompts import HumanMessagePromptTemplate
from langchain.schema.messages import SystemMessage
from tqdm import tqdm

# Load documents
reports = pyreadr.read_r('./demo_reports.rdata')
text = reports['demo_reports']
text["noteID"] = list(range(0,len(text)))

# Initialize embedding function
embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# Initialize prompt
QA_CHAIN_PROMPT = PromptTemplate(input_variables=['context', 'question'], template="""
<|im_start|>system
You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise.
<|im_end|>
<|im_start|>user
Question: {question}
Context: {context}
<|im_end|>
<|im_start|>assistant
""")

# Initialize LLM
llm = Ollama(
    model="mistral-openorca", # Uses the LLM model, "Mistral-7B-OpenOrca" on the Ollama server. 
    callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]), # For real-time response generation
    temperature = 0, # Sets variability of responses to 0
    num_gpu = 50, # Number of layers to offload onto the GPU
    stop = ["<|im_end|>"] # Ensures that the LLM stops when the token <|im_end|> is generated
)
# QA chain
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)
rag_chain_from_docs = (
    RunnablePassthrough.assign(context=(lambda x: format_docs(x["context"])))
    | QA_CHAIN_PROMPT
    | llm
    | StrOutputParser() # Formats so that the output is a string
)

#Initialize questions
question_colitis = "Immune checkpoint inhibitor induced colitis is an immune-related adverse event characterized by colitis, diarrhea, or increased ostomy output as a direct result of immune checkpoint inhibitor therapy. Patients may have findings of inflammation on colon biopsy. Based on the medical reports provided in the context, is the patient currently experiencing immune checkpoint inhibitor induced colitis? Output your answer as either 'Answer: Yes' or 'Answer: No'. Explain your reasoning."

question_hepatitis = "Immune checkpoint inhibitor induced hepatitis is an immune-related adverse event characterized by liver inflammation, hepatotoxicity and/or hepatitis as a direct result of immune checkpoint inhibitor therapy. Patients may present with transaminitis, elevated LFTs, and have findings of inflammation on liver biopsy. Based on the medical reports provided in the context, is the patient currently experiencing immune checkpoint inhibitor induced hepatitis? Output your answer as either 'Answer: Yes' or 'Answer: No'. Explain your reasoning."

question_myocarditis = "Immune checkpoint inhibitor induced myocarditis is an immune-related adverse event characterized by myocarditis as a direct result of immune checkpoint inhibitor therapy. Patients may present with arrhythmia, heart failure and elevated cardiac biomarkers, such as troponin and BNP. Patients may also have a cardiac MRI or cardiac biopsy with signs of heart inflammation. Based on the medical reports provided in the context, is the patient currently experiencing immune checkpoint inhibitor induced myocarditis? Output your answer as either 'Answer: Yes' or 'Answer: No'. Explain your reasoning."

question_pneumonitis = "Immune checkpoint inhibitor induced pneumonitis is an immune-related adverse event characterized by pneumonitis as a direct result of immune checkpoint inhibitor therapy. Patients may have chest X-ray (CXR) or CT findings suggestive of pneumonitis. Based on the medical reports provided in the context, is the patient currently experiencing immune checkpoint inhibitor induced pneumonitis? Output your answer as either 'Answer: Yes' or 'Answer: No'. Explain your reasoning."

# Create empty dataframe to store results
results = pd.DataFrame(columns=['Patient_ID', 'Adjudicated_Case', 
                                'Answer_Colitis', 'Source_Colitis',
                                'Answer_Hepatitis', 'Source_Hepatitis',
                                'Answer_Myocarditis', 'Source_Myocarditis',
                                'Answer_Pneumonitis','Source_Pneumonitis'])

# Iterate through each patient
for i in tqdm(text["Patient_ID"].unique()):
    # Load text from patient encounter
    encounter = text[text["Patient_ID"] == i]
    documents = encounter["Text"]
    
    # Split text into 1000-character chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_splits = text_splitter.create_documents(documents)
    
    # Store text segments in a vector database
    vectorstore = Chroma.from_documents(documents=all_splits, embedding=embedding_function)
    
    # Instruct LLM to augment prompt with context retrieved from vectorstore
    rag_chain_with_source = RunnableParallel(
        {"context": vectorstore.as_retriever(), "question": RunnablePassthrough()}
    ).assign(answer=rag_chain_from_docs)
    
    # Invoke LLM to detect ICI Colitis
    try:
        print("Does the patient have ICI colitis?")
        response_colitis = rag_chain_with_source.invoke(question_colitis)
        print()
    except ValueError:
        response_colitis = {"question": question_colitis,"answer": "xxxxx", "context": "xxxxx"}
        
    # Invoke LLM to detect ICI Hepatitis
    try:
        print("Does the patient have ICI hepatitis?")
        response_hepatitis = rag_chain_with_source.invoke(question_hepatitis)
        print()
    except ValueError:
        response_hepatitis = {"question": question_hepatitis,"answer": "xxxxx", "context": "xxxxx"}
        
    # Invoke LLM to detect ICI Myocarditis
    try:
        print("Does the patient have ICI myocarditis?")
        response_myocarditis = rag_chain_with_source.invoke(question_myocarditis)
        print()
    except ValueError:
        response_myocarditis = {"question": question_myocarditis,"answer": "xxxxx", "context": "xxxxx"}
        
    # Invoke LLM to detect ICI Pneumonitis
    try:
        print("Does the patient have ICI pneumonitis?")
        response_pneumonitis = rag_chain_with_source.invoke(question_pneumonitis)
        print()
    except ValueError:
        response_pneumonitis = {"question": question_pneumonitis,"answer": "xxxxx", "context": "xxxxx"}

    results.loc[len(results.index)] = [i, 
                             encounter.iloc[0,encounter.columns.get_loc("Adjudicated_Case")],
                             response_colitis["answer"], response_colitis["context"],
                             response_hepatitis["answer"], response_hepatitis["context"],
                             response_myocarditis["answer"], response_myocarditis["context"],
                             response_pneumonitis["answer"], response_pneumonitis["context"]]
    
    vectorstore.delete_collection()
    
results.to_csv('./demo_LLM_loop_results.csv')
