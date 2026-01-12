import fitz
from PIL import Image
import imagehash
import io
import os


HRDC_LOGO_PATH = "assets/hrdc_logo.png"
HRDC_HASH_THRESHOLD = 10  


def detect_hrdc_logo(pdf_path):
    import fitz
    import os
    import io
    from PIL import Image
    import imagehash

    HRDC_LOGO_PATH = "assets/hrdc_logo.png"
    HRDC_HASH_THRESHOLD = 25

    ref_img = Image.open(HRDC_LOGO_PATH).convert("RGB")
    ref_hash = imagehash.phash(ref_img)

    doc = fitz.open(pdf_path)

    for page_idx, page in enumerate(doc[:2]):
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]
            base = doc.extract_image(xref)
            image_bytes = base["image"]

            try:
                img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img_hash = imagehash.phash(img_pil)
                distance = abs(ref_hash - img_hash)


                if distance <= HRDC_HASH_THRESHOLD:
                    return True
            except Exception as e:
                continue
    return False

