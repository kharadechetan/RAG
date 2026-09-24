import os
import requests
import fitz  # PyMuPDF

urls = [
    "https://www.ibiblio.org/ebooks/Austen/Emma/Austen_Emma.pdf",
    "https://www.ibiblio.org/ebooks/Austen/Pride/Austen_Pride.pdf",
    "https://www.ibiblio.org/ebooks/Dostoyevsky/Crime/Crime.pdf",
    "https://www.ibiblio.org/ebooks/Melville/Moby/Moby.pdf",
    "https://www.ibiblio.org/ebooks/Tolstoy/War/War.pdf",
    "https://www.ibiblio.org/ebooks/Hugo/LesMis/LesMis.pdf",
    "https://www.ibiblio.org/ebooks/Defoe/Crusoe/Crusoe.pdf",
    "https://www.ibiblio.org/ebooks/Twain/Finn/Finn.pdf",
    "https://www.ibiblio.org/ebooks/Dickens/Cities/Cities.pdf",
    "https://www.ibiblio.org/ebooks/Eliot/Middlemarch/Middlemarch.pdf"
]

output_dir = r"b:\navgurukul\chatbot\test_data\real_books"
os.makedirs(output_dir, exist_ok=True)

valid_pdfs = []
for url in urls:
    name = url.split("/")[-1]
    path = os.path.join(output_dir, name)
    print(f"Downloading {name}...")
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                f.write(resp.content)
            
            doc = fitz.open(path)
            num_pages = len(doc)
            doc.close()
            
            print(f"{name} has {num_pages} pages.")
            if num_pages >= 200:
                valid_pdfs.append(path)
            else:
                print(f"  -> Discarding {name} because it has only {num_pages} pages.")
                os.remove(path)
        else:
            print(f"Failed to download {name} - status {resp.status_code}")
    except Exception as e:
        print(f"Error downloading {name}: {e}")

print(f"\nSuccessfully downloaded {len(valid_pdfs)} PDFs with >= 200 pages.")
