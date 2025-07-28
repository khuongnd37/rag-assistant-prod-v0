
# Giả định phần đầu file đầy đủ
class DocumentProcessor:
    def process_txt(self, file_path: str, encoding: str = 'utf-8', use_langchain: bool = True):
        # giả lập xử lý
        documents = []
        chunks = [Document("Hello world!"), Document("   "), Document("������"), Document("AI is great")]
        for idx, chunk in enumerate(chunks):
            # ✅ Lọc chunk "rác"
            if len(chunk.page_content.strip()) < 50 or not any(c.isalnum() for c in chunk.page_content):
                continue
            chunk.metadata = {'chunk_index': idx}
            documents.append(chunk)
        return documents

# Dummy Document class để test
class Document:
    def __init__(self, page_content):
        self.page_content = page_content
        self.metadata = {}
