import os
from typing import List
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

class ContextRetriever:
    def __init__(self, docs_dir: str = "docs", persist_dir: str = "db"):
        self.docs_dir = docs_dir
        self.persist_dir = persist_dir
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        self.vectorstore = None
        
        if os.path.exists(self.persist_dir):
            self.vectorstore = Chroma(persist_directory=self.persist_dir, embedding_function=self.embeddings)
        else:
            self.initialize_index()

    def initialize_index(self):
        """
        Loads all markdown files from docs_dir and creates a vector index.
        """
        all_docs = []
        for file in os.listdir(self.docs_dir):
            if file.endswith(".md"):
                loader = TextLoader(os.path.join(self.docs_dir, file))
                all_docs.extend(loader.load())

        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        docs = text_splitter.split_documents(all_docs)
        
        self.vectorstore = Chroma.from_documents(
            documents=docs, 
            embedding=self.embeddings,
            persist_directory=self.persist_dir
        )

    def get_context(self, query: str, k: int = 3) -> str:
        """
        Retrieves the most relevant documentation snippets for a given query.
        """
        if not self.vectorstore:
            return ""
            
        docs = self.vectorstore.similarity_search(query, k=k)
        context = "\n\n".join([doc.page_content for doc in docs])
        return f"## Relevant Documentation Context:\n{context}\n"

if __name__ == "__main__":
    # Example usage
    # retriever = ContextRetriever()
    # print(retriever.get_context("How to move the camera in 3D?"))
    pass
