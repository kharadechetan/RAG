import os
import requests
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

def fetch_wikipedia_articles(num_articles=20):
    text = ""
    # Use the extract API to get plain text
    url = "https://en.wikipedia.org/w/api.php?action=query&generator=random&grnnamespace=0&prop=extracts&explaintext=1&format=json&grnlimit=" + str(num_articles)
    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            title = page_info.get("title", "Unknown")
            extract = page_info.get("extract", "")
            if extract:
                text += f"{title}\n\n{extract}\n\n"
    except Exception as e:
        print(f"Error fetching wiki: {e}")
    return text

def create_pdf(filename, num_pages_target=200):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    
    story = []
    
    # We will fetch articles until we hit ~100,000 words which is roughly 200 pages (approx 500 words per page).
    # Since network calls take time, we can fetch once and repeat the text, but the user said "Do not generate 200-page PDFs by duplicating the same page just to pass the requirement."
    # So we'll fetch unique articles.
    
    # Actually, fetching 200 pages of unique Wiki text might take a lot of API calls.
    # Let's download a large public domain text file from Project Gutenberg instead.
    # E.g. The Complete Works of William Shakespeare (about 5MB of text) -> covers all 10 PDFs easily!
    
    print(f"Generating {filename}...")
    try:
        r = requests.get("https://www.gutenberg.org/cache/epub/100/pg100.txt", timeout=60)
        full_text = r.text
        
        # Slice the text differently for each PDF so they are distinct but large
        import random
        start_idx = random.randint(0, len(full_text) // 2)
        text_chunk = full_text[start_idx:start_idx + 600000] # ~600k chars is about 200 pages
        
        paragraphs = text_chunk.split("\n\n")
        for p in paragraphs:
            p = p.strip()
            if p:
                # Replace newlines with spaces for reportlab
                p = p.replace("\n", " ")
                story.append(Paragraph(p, normal_style))
                story.append(Spacer(1, 12))
        
        doc.build(story)
        print(f"Saved {filename}")
    except Exception as e:
        print(f"Failed to generate {filename}: {e}")

output_dir = r"b:\navgurukul\chatbot\test_data\real_books"
os.makedirs(output_dir, exist_ok=True)

for i in range(10):
    create_pdf(os.path.join(output_dir, f"generated_book_{i+1}.pdf"))
