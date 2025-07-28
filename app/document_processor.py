
# Giáº£ Ä‘á»‹nh pháº§n Ä‘áº§u file Ä‘áº§y Ä‘á»§
class DocumentProcessor:
    def process_txt(self, file_path: str, encoding: str = 'utf-8', use_langchain: bool = True):
        # giáº£ láº­p xá»­ lÃ½
        documents = []
        chunks = [Document("Hello world!"), Document("   "), Document("í ½í´¥í ½í´¥í ½í´¥"), Document("AI is great")]
        for idx, chunk in enumerate(chunks):
            # âœ… Lá»c chunk "rÃ¡c"
            if len(chunk.page_content.strip()) < 50 or not any(c.isalnum() for c in chunk.page_content):
                continue
            chunk.metadata = {'chunk_index': idx}
            documents.append(chunk)
        return documents

# Dummy Document class Ä‘á»ƒ test
class Document:
    def __init__(self, page_content):
        self.page_content = page_content
        self.metadata = {}
