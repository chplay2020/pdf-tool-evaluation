#!/usr/bin/env python3
"""
Auto-Tagging Module - Automatic Content Classification
======================================================

This module analyzes text content and automatically assigns relevant tags
based on keyword matching and content patterns. Supports multiple domains:
- Y học (Medicine)
- Công nghệ thông tin (IT)
- Kinh tế - Tài chính (Economics & Finance)
- Luật (Law)
- Giáo dục (Education)
- Khoa học kỹ thuật (Engineering)
- And more...

Features:
- Multi-domain tag detection
- Domain classification (auto-detect document field)
- Source type classification
- Configurable tag categories and keywords

Author: Research Assistant
Date: January 2026
"""

import re
from typing import Any


# =============================================================================
# DOMAIN DEFINITIONS - Phân loại lĩnh vực chính
# =============================================================================
DOMAIN_DEFINITIONS: dict[str, list[str]] = {
    "Y học": [
        "y học", "y tế", "bệnh viện", "bác sĩ", "điều trị", "chẩn đoán",
        "thuốc", "bệnh nhân", "lâm sàng", "phẫu thuật", "y khoa", "sức khỏe",
        "medical", "medicine", "healthcare", "hospital", "doctor", "patient"
    ],
    "Công nghệ thông tin": [
        "công nghệ thông tin", "CNTT", "phần mềm", "lập trình", "máy tính",
        "dữ liệu", "database", "software", "programming", "IT", "computer",
        "internet", "web", "app", "cloud", "AI", "machine learning"
    ],
    "Kinh tế - Tài chính": [
        "kinh tế", "tài chính", "ngân hàng", "đầu tư", "chứng khoán",
        "thị trường", "doanh nghiệp", "kinh doanh", "thương mại", "xuất nhập khẩu",
        "economics", "finance", "banking", "investment", "stock", "business"
    ],
    "Luật": [
        "luật", "pháp luật", "quy định", "nghị định", "thông tư", "hiến pháp",
        "tòa án", "luật sư", "hợp đồng", "vi phạm", "hình sự", "dân sự",
        "law", "legal", "regulation", "court", "attorney", "contract"
    ],
    "Giáo dục": [
        "giáo dục", "đào tạo", "trường học", "đại học", "sinh viên", "học sinh",
        "giảng viên", "giáo viên", "chương trình", "học tập", "thi cử",
        "education", "training", "university", "student", "teacher", "learning"
    ],
    "Khoa học kỹ thuật": [
        "kỹ thuật", "công nghệ", "kỹ sư", "engineering", "technical",
        "cơ khí", "điện", "điện tử", "tự động hóa", "robot"
    ],
    "Nông nghiệp": [
        "nông nghiệp", "trồng trọt", "chăn nuôi", "nông sản", "cây trồng",
        "vật nuôi", "agriculture", "farming", "crop", "livestock"
    ],
    "Xây dựng": [
        "xây dựng", "kiến trúc", "công trình", "nhà ở", "bất động sản",
        "construction", "architecture", "building", "real estate"
    ],
    "Du lịch - Khách sạn": [
        "du lịch", "khách sạn", "nhà hàng", "resort", "tourism", "hotel",
        "travel", "hospitality", "tour"
    ],
    "Môi trường": [
        "môi trường", "sinh thái", "ô nhiễm", "khí hậu", "biến đổi khí hậu",
        "environment", "ecology", "pollution", "climate"
    ],
}


# =============================================================================
# TAG DEFINITIONS - Chi tiết tags theo từng lĩnh vực
# =============================================================================
TAG_DEFINITIONS: dict[str, list[str]] = {
    
    # =========================================================================
    # LĨNH VỰC: Y HỌC
    # =========================================================================
    
    # --- Chuyên khoa ---
    "Tim mạch": [
        "tim mạch", "tim", "mạch máu", "động mạch", "tĩnh mạch", 
        "van tim", "nhồi máu", "suy tim", "loạn nhịp", "rung nhĩ",
        "nhĩ", "thất", "động mạch vành", "cardiovascular", "cardiac",
        "ECG", "điện tâm đồ", "siêu âm tim", "cấy ghép tim", "stent"
    ],
    "Huyết áp": [
        "huyết áp", "tăng huyết áp", "hạ huyết áp", "cao huyết áp",
        "huyết áp tâm thu", "huyết áp tâm trương", "hypertension",
        "hypotension", "blood pressure", "mmHg"
    ],
    "Hô hấp": [
        "hô hấp", "phổi", "phế quản", "viêm phổi", "hen suyễn",
        "COPD", "khó thở", "thở máy", "oxy", "pneumonia", "asthma",
        "thông khí", "respiratory"
    ],
    "Tiêu hóa": [
        "tiêu hóa", "dạ dày", "ruột", "gan", "mật", "tụy",
        "viêm gan", "xơ gan", "viêm loét", "trào ngược", "táo bón",
        "tiêu chảy", "hepatitis", "gastric"
    ],
    "Thần kinh": [
        "thần kinh", "não", "tủy sống", "đột quỵ", "Parkinson",
        "Alzheimer", "động kinh", "migraine", "đau đầu", "stroke",
        "neurological", "neurology"
    ],
    "Nội tiết": [
        "nội tiết", "đái tháo đường", "tiểu đường", "tuyến giáp",
        "insulin", "glucose", "HbA1c", "diabetes", "thyroid",
        "hormone", "cortisol"
    ],
    "Thận - Tiết niệu": [
        "thận", "tiết niệu", "suy thận", "lọc máu", "thẩm phân",
        "creatinine", "GFR", "protein niệu", "kidney", "renal",
        "dialysis", "nephrology"
    ],
    "Cơ xương khớp": [
        "cơ xương khớp", "xương", "khớp", "viêm khớp", "loãng xương",
        "gout", "thấp khớp", "thoái hóa", "orthopedic", "arthritis"
    ],
    "Ung bướu": [
        "ung thư", "ung bướu", "khối u", "hóa trị", "xạ trị",
        "di căn", "cancer", "tumor", "oncology", "chemotherapy"
    ],
    "Da liễu": [
        "da liễu", "da", "nấm", "vảy nến", "eczema", "mụn",
        "dermatology", "skin", "psoriasis"
    ],
    "Mắt": [
        "mắt", "nhãn khoa", "đục thủy tinh thể", "glaucoma",
        "cận thị", "viễn thị", "võng mạc", "ophthalmology"
    ],
    "Tai mũi họng": [
        "tai mũi họng", "viêm họng", "viêm xoang", "viêm tai",
        "ENT", "otolaryngology", "sinusitis"
    ],
    "Nhi khoa": [
        "nhi khoa", "trẻ em", "sơ sinh", "pediatric", "infant",
        "trẻ sơ sinh", "tiêm chủng"
    ],
    "Sản phụ khoa": [
        "sản phụ khoa", "thai kỳ", "sinh", "phụ nữ", "gynecology",
        "obstetrics", "pregnancy", "childbirth"
    ],
    "Truyền nhiễm": [
        "truyền nhiễm", "nhiễm trùng", "vi khuẩn", "virus", "kháng sinh",
        "infectious", "infection", "antibiotic", "COVID", "HIV", "AIDS"
    ],
    "Huyết học": [
        "huyết học", "máu", "thiếu máu", "đông máu", "bạch cầu",
        "hồng cầu", "tiểu cầu", "hematology", "anemia", "leukemia"
    ],
    "Dị ứng - Miễn dịch": [
        "dị ứng", "miễn dịch", "sốc phản vệ", "allergy", "immune",
        "autoimmune", "lupus"
    ],
    
    # --- Y học: Loại can thiệp ---
    "Điều trị nội khoa": [
        "điều trị nội khoa", "thuốc", "dược", "liều", "dose",
        "medication", "drug", "pharmaceutical"
    ],
    "Can thiệp - Phẫu thuật": [
        "phẫu thuật", "can thiệp", "mổ", "surgery", "intervention",
        "procedure", "operation", "nội soi"
    ],
    "Chẩn đoán y khoa": [
        "chẩn đoán", "xét nghiệm", "diagnostic", "test", "diagnosis",
        "imaging", "hình ảnh y khoa", "MRI", "CT", "X-quang"
    ],
    "Phòng ngừa - Dự phòng": [
        "phòng ngừa", "dự phòng", "prevention", "prophylaxis",
        "vaccine", "vắc xin", "tiêm phòng"
    ],
    "Cấp cứu - Hồi sức": [
        "cấp cứu", "emergency", "hồi sức", "ICU", "resuscitation",
        "acute", "cấp tính"
    ],
    "Phác đồ Bộ Y Tế": [
        "phác đồ", "bộ y tế", "hướng dẫn điều trị", "quy trình y tế",
        "protocol", "guideline", "ministry of health", "MOH"
    ],
    
    # =========================================================================
    # LĨNH VỰC: CÔNG NGHỆ THÔNG TIN
    # =========================================================================
    
    # --- Lập trình ---
    "Lập trình": [
        "lập trình", "programming", "code", "coding", "developer",
        "phát triển phần mềm", "software development"
    ],
    "Python": [
        "python", "django", "flask", "pandas", "numpy", "pytorch",
        "tensorflow", "jupyter", "pip"
    ],
    "JavaScript": [
        "javascript", "nodejs", "node.js", "react", "vue", "angular",
        "typescript", "npm", "express"
    ],
    "Java": [
        "java", "spring", "spring boot", "maven", "gradle", "jvm",
        "hibernate", "kotlin"
    ],
    "C/C++": [
        "c++", "c programming", "pointer", "memory management",
        "gcc", "makefile"
    ],
    
    # --- Hệ thống & Hạ tầng ---
    "Database": [
        "database", "cơ sở dữ liệu", "SQL", "MySQL", "PostgreSQL",
        "MongoDB", "Redis", "NoSQL", "query", "table", "index"
    ],
    "Cloud Computing": [
        "cloud", "đám mây", "AWS", "Azure", "GCP", "Google Cloud",
        "serverless", "lambda", "S3", "EC2", "kubernetes", "docker"
    ],
    "DevOps": [
        "devops", "CI/CD", "continuous integration", "deployment",
        "jenkins", "gitlab", "github actions", "terraform", "ansible"
    ],
    "Mạng máy tính": [
        "network", "mạng", "TCP/IP", "HTTP", "DNS", "firewall",
        "router", "switch", "VPN", "load balancer"
    ],
    "Bảo mật": [
        "security", "bảo mật", "cybersecurity", "encryption", "mã hóa",
        "authentication", "authorization", "SSL", "TLS", "hacking"
    ],
    
    # --- AI & Data ---
    "Trí tuệ nhân tạo": [
        "AI", "artificial intelligence", "trí tuệ nhân tạo",
        "machine learning", "học máy", "deep learning", "neural network",
        "mạng neural", "NLP", "computer vision"
    ],
    "Data Science": [
        "data science", "khoa học dữ liệu", "data analysis", "phân tích dữ liệu",
        "big data", "data mining", "visualization", "trực quan hóa"
    ],
    "Blockchain": [
        "blockchain", "crypto", "cryptocurrency", "bitcoin", "ethereum",
        "smart contract", "NFT", "DeFi", "web3"
    ],
    
    # --- Phát triển ứng dụng ---
    "Web Development": [
        "web", "website", "frontend", "backend", "fullstack",
        "HTML", "CSS", "responsive", "API", "REST"
    ],
    "Mobile Development": [
        "mobile", "ứng dụng di động", "iOS", "Android", "React Native",
        "Flutter", "Swift", "Kotlin mobile"
    ],
    "Game Development": [
        "game", "game development", "Unity", "Unreal", "game engine",
        "2D", "3D", "VR", "AR"
    ],
    
    # =========================================================================
    # LĨNH VỰC: KINH TẾ - TÀI CHÍNH
    # =========================================================================
    
    # --- Tài chính ---
    "Ngân hàng": [
        "ngân hàng", "bank", "banking", "tín dụng", "credit",
        "tiền gửi", "deposit", "khoản vay", "loan", "lãi suất", "interest rate"
    ],
    "Chứng khoán": [
        "chứng khoán", "stock", "cổ phiếu", "share", "thị trường chứng khoán",
        "stock market", "sàn giao dịch", "VN-Index", "trader"
    ],
    "Đầu tư": [
        "đầu tư", "investment", "investor", "nhà đầu tư", "portfolio",
        "danh mục", "quỹ đầu tư", "fund", "ROI", "return"
    ],
    "Bảo hiểm": [
        "bảo hiểm", "insurance", "premium", "phí bảo hiểm", "claim",
        "bồi thường", "rủi ro", "risk"
    ],
    "Fintech": [
        "fintech", "công nghệ tài chính", "e-wallet", "ví điện tử",
        "payment", "thanh toán", "mobile banking"
    ],
    
    # --- Kinh tế vĩ mô ---
    "Kinh tế vĩ mô": [
        "kinh tế vĩ mô", "macroeconomics", "GDP", "lạm phát", "inflation",
        "tăng trưởng", "growth", "chính sách tiền tệ", "monetary policy"
    ],
    "Thương mại quốc tế": [
        "thương mại quốc tế", "xuất khẩu", "nhập khẩu", "export", "import",
        "FTA", "WTO", "hải quan", "customs", "thuế quan", "tariff"
    ],
    "Kinh tế vi mô": [
        "kinh tế vi mô", "microeconomics", "cung cầu", "supply demand",
        "giá cả", "price", "thị trường", "market"
    ],
    
    # --- Doanh nghiệp ---
    "Quản trị doanh nghiệp": [
        "quản trị", "management", "doanh nghiệp", "enterprise", "CEO",
        "chiến lược", "strategy", "tổ chức", "organization"
    ],
    "Marketing": [
        "marketing", "tiếp thị", "quảng cáo", "advertising", "brand",
        "thương hiệu", "digital marketing", "SEO", "social media"
    ],
    "Kế toán - Kiểm toán": [
        "kế toán", "accounting", "kiểm toán", "audit", "sổ sách",
        "báo cáo tài chính", "financial report", "thuế", "tax"
    ],
    "Nhân sự": [
        "nhân sự", "HR", "human resource", "tuyển dụng", "recruitment",
        "đào tạo nhân viên", "lương", "salary", "KPI"
    ],
    "Khởi nghiệp": [
        "khởi nghiệp", "startup", "entrepreneur", "founder", "venture capital",
        "VC", "pitch", "scale up"
    ],
    
    # =========================================================================
    # LĨNH VỰC: LUẬT
    # =========================================================================
    
    "Luật Dân sự": [
        "luật dân sự", "civil law", "hợp đồng", "contract", "tài sản",
        "property", "thừa kế", "inheritance", "quyền sở hữu"
    ],
    "Luật Hình sự": [
        "luật hình sự", "criminal law", "tội phạm", "crime", "hình phạt",
        "punishment", "án tù", "prison", "khởi tố"
    ],
    "Luật Thương mại": [
        "luật thương mại", "commercial law", "luật doanh nghiệp",
        "corporate law", "phá sản", "bankruptcy", "sáp nhập", "merger"
    ],
    "Luật Lao động": [
        "luật lao động", "labor law", "hợp đồng lao động", "employment",
        "sa thải", "termination", "bảo hiểm xã hội", "social insurance"
    ],
    "Luật Hành chính": [
        "luật hành chính", "administrative law", "nghị định", "decree",
        "thông tư", "circular", "quyết định", "decision"
    ],
    "Luật Đất đai": [
        "luật đất đai", "land law", "quyền sử dụng đất", "land use right",
        "sổ đỏ", "giấy chứng nhận", "quy hoạch", "planning"
    ],
    "Sở hữu trí tuệ": [
        "sở hữu trí tuệ", "intellectual property", "IP", "bằng sáng chế",
        "patent", "bản quyền", "copyright", "thương hiệu", "trademark"
    ],
    
    # =========================================================================
    # LĨNH VỰC: GIÁO DỤC
    # =========================================================================
    
    "Giáo dục phổ thông": [
        "giáo dục phổ thông", "trung học", "tiểu học", "THPT", "THCS",
        "high school", "primary school", "secondary school"
    ],
    "Giáo dục đại học": [
        "đại học", "university", "cao đẳng", "college", "sinh viên",
        "student", "giảng viên", "lecturer", "học phần", "tín chỉ"
    ],
    "Giáo dục nghề nghiệp": [
        "đào tạo nghề", "vocational", "kỹ năng nghề", "chứng chỉ",
        "certificate", "thực hành"
    ],
    "E-Learning": [
        "e-learning", "học trực tuyến", "online learning", "MOOC",
        "khóa học online", "LMS", "video bài giảng"
    ],
    "Nghiên cứu học thuật": [
        "nghiên cứu", "research", "luận văn", "thesis", "luận án",
        "dissertation", "công bố", "publication", "journal"
    ],
    "Phương pháp giảng dạy": [
        "phương pháp giảng dạy", "teaching method", "sư phạm",
        "pedagogy", "đánh giá", "assessment", "kiểm tra"
    ],
    
    # =========================================================================
    # LĨNH VỰC: KHOA HỌC KỸ THUẬT
    # =========================================================================
    
    "Cơ khí": [
        "cơ khí", "mechanical", "máy móc", "machine", "động cơ", "engine",
        "gia công", "manufacturing", "CNC"
    ],
    "Điện - Điện tử": [
        "điện", "electrical", "điện tử", "electronics", "mạch điện",
        "circuit", "IC", "chip", "PCB", "vi xử lý"
    ],
    "Tự động hóa": [
        "tự động hóa", "automation", "PLC", "SCADA", "robot",
        "robotics", "IoT", "sensor", "cảm biến"
    ],
    "Hóa học - Hóa công": [
        "hóa học", "chemistry", "chemical", "phản ứng", "reaction",
        "chất hóa học", "polymer", "vật liệu"
    ],
    "Vật lý": [
        "vật lý", "physics", "cơ học", "mechanics", "nhiệt động học",
        "thermodynamics", "quang học", "optics", "lượng tử", "quantum"
    ],
    "Toán học": [
        "toán học", "mathematics", "đại số", "algebra", "giải tích",
        "calculus", "thống kê", "statistics", "xác suất", "probability"
    ],
    
    # =========================================================================
    # LĨNH VỰC: NÔNG NGHIỆP
    # =========================================================================
    
    "Trồng trọt": [
        "trồng trọt", "cultivation", "cây trồng", "crop", "giống cây",
        "seed", "phân bón", "fertilizer", "thuốc trừ sâu", "pesticide"
    ],
    "Chăn nuôi": [
        "chăn nuôi", "livestock", "gia súc", "cattle", "gia cầm",
        "poultry", "thức ăn chăn nuôi", "feed"
    ],
    "Thủy sản": [
        "thủy sản", "aquaculture", "nuôi trồng thủy sản", "cá", "fish",
        "tôm", "shrimp", "ao nuôi"
    ],
    "Nông nghiệp công nghệ cao": [
        "nông nghiệp công nghệ cao", "smart farming", "nhà kính",
        "greenhouse", "tưới tiêu tự động", "precision agriculture"
    ],
    
    # =========================================================================
    # LĨNH VỰC: XÂY DỰNG - BẤT ĐỘNG SẢN
    # =========================================================================
    
    "Kiến trúc": [
        "kiến trúc", "architecture", "thiết kế", "design", "bản vẽ",
        "drawing", "quy hoạch", "urban planning"
    ],
    "Xây dựng dân dụng": [
        "xây dựng dân dụng", "civil construction", "nhà ở", "housing",
        "chung cư", "apartment", "biệt thự", "villa"
    ],
    "Xây dựng công nghiệp": [
        "xây dựng công nghiệp", "industrial construction", "nhà máy",
        "factory", "kho bãi", "warehouse"
    ],
    "Bất động sản": [
        "bất động sản", "real estate", "mua bán nhà", "property",
        "cho thuê", "rental", "môi giới", "broker"
    ],
    
    # =========================================================================
    # LĨNH VỰC: MÔI TRƯỜNG
    # =========================================================================
    
    "Biến đổi khí hậu": [
        "biến đổi khí hậu", "climate change", "hiệu ứng nhà kính",
        "greenhouse effect", "carbon", "CO2", "nóng lên toàn cầu"
    ],
    "Xử lý ô nhiễm": [
        "ô nhiễm", "pollution", "xử lý nước thải", "wastewater",
        "xử lý rác", "waste treatment", "khí thải", "emission"
    ],
    "Năng lượng tái tạo": [
        "năng lượng tái tạo", "renewable energy", "năng lượng mặt trời",
        "solar", "điện gió", "wind power", "năng lượng sạch"
    ],
    "Bảo tồn": [
        "bảo tồn", "conservation", "đa dạng sinh học", "biodiversity",
        "khu bảo tồn", "wildlife", "động vật hoang dã"
    ],
    
    # =========================================================================
    # LOẠI TÀI LIỆU (áp dụng chung)
    # =========================================================================
    
    "Nghiên cứu - Báo cáo": [
        "nghiên cứu", "research", "báo cáo", "report", "phân tích",
        "analysis", "survey", "khảo sát"
    ],
    "Giáo trình - Sách": [
        "giáo trình", "textbook", "sách", "book", "chương", "chapter",
        "bài giảng", "lecture"
    ],
    "Hướng dẫn - Quy trình": [
        "hướng dẫn", "guide", "manual", "quy trình", "procedure",
        "hướng dẫn sử dụng", "tutorial"
    ],
    "Văn bản pháp quy": [
        "văn bản pháp quy", "legal document", "nghị định", "decree",
        "thông tư", "circular", "luật", "law", "quyết định"
    ],
    "Tin tức - Bài viết": [
        "tin tức", "news", "bài viết", "article", "blog", "báo chí",
        "press", "media"
    ],
}


def normalize_text(text: str) -> str:
    """
    Normalize text for keyword matching.
    
    Args:
        text: Input text
        
    Returns:
        Normalized lowercase text
    """
    # Convert to lowercase
    text = text.lower()
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def extract_tags_from_content(content: str, min_keyword_matches: int = 1) -> list[str]:
    """
    Extract relevant tags from content based on keyword matching.
    
    Args:
        content: Text content to analyze
        min_keyword_matches: Minimum keyword matches required to assign a tag
        
    Returns:
        List of matched tags sorted by relevance
    """
    normalized_content = normalize_text(content)
    tag_scores: dict[str, int] = {}
    
    for tag, keywords in TAG_DEFINITIONS.items():
        match_count = 0
        for keyword in keywords:
            # Use word boundary matching for more accurate results
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            matches = len(re.findall(pattern, normalized_content))
            match_count += matches
        
        if match_count >= min_keyword_matches:
            tag_scores[tag] = match_count
    
    # Sort by match count (most relevant first)
    sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return only tag names
    return [tag for tag, _ in sorted_tags]


def extract_tags_from_section(section_heading: str) -> list[str]:
    """
    Extract tags specifically from section headings.
    
    Section headings often contain key topic indicators.
    
    Args:
        section_heading: Section/heading text
        
    Returns:
        List of matched tags
    """
    if not section_heading:
        return []
    
    return extract_tags_from_content(section_heading, min_keyword_matches=1)


def detect_domain(content: str, source_file: str = "") -> list[tuple[str, int]]:
    """
    Detect the primary domain/field of the content.
    
    Args:
        content: Text content to analyze
        source_file: Source filename for additional context
        
    Returns:
        List of (domain, score) tuples sorted by relevance
    """
    normalized_content = normalize_text(content + " " + source_file)
    domain_scores: dict[str, int] = {}
    
    for domain, keywords in DOMAIN_DEFINITIONS.items():
        match_count = 0
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            matches = len(re.findall(pattern, normalized_content))
            match_count += matches
        
        if match_count > 0:
            domain_scores[domain] = match_count
    
    # Sort by score
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_domains


def get_primary_domain(content: str, source_file: str = "") -> str:
    """
    Get the primary domain of the content.
    
    Args:
        content: Text content
        source_file: Source filename
        
    Returns:
        Primary domain name or "Khác" if not detected
    """
    domains = detect_domain(content, source_file)
    if domains:
        return domains[0][0]
    return "Khác"


def auto_tag_content(
    content: str,
    section: str = "",
    source_file: str = "",
    max_tags: int = 10
) -> list[str]:
    """
    Automatically generate tags for content.
    
    Combines analysis of:
    - Main content
    - Section heading
    - Source filename
    
    Args:
        content: Main text content
        section: Section heading (optional)
        source_file: Source filename (optional)
        max_tags: Maximum number of tags to return
        
    Returns:
        List of relevant tags
    """
    all_tags: dict[str, int] = {}
    
    # Extract from main content (most important)
    content_tags = extract_tags_from_content(content, min_keyword_matches=2)
    for i, tag in enumerate(content_tags):
        # Give higher weight to earlier matches
        all_tags[tag] = all_tags.get(tag, 0) + (10 - min(i, 9))
    
    # Extract from section heading (high importance)
    section_tags = extract_tags_from_section(section)
    for tag in section_tags:
        all_tags[tag] = all_tags.get(tag, 0) + 5
    
    # Extract from source filename
    if source_file:
        filename_tags = extract_tags_from_content(source_file, min_keyword_matches=1)
        for tag in filename_tags:
            all_tags[tag] = all_tags.get(tag, 0) + 3
    
    # Sort by score and return top tags
    sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
    
    return [tag for tag, _ in sorted_tags[:max_tags]]


def auto_tag_node(node: dict[str, Any], source_file: str = "") -> list[str]:
    """
    Automatically generate tags for a node.
    
    Args:
        node: Node dictionary with 'content' and optionally 'section'
        source_file: Source filename
        
    Returns:
        List of relevant tags
    """
    content = node.get("content", "")
    section = node.get("section", "")
    
    return auto_tag_content(content, section, source_file)


def add_tags_to_nodes(
    nodes: list[dict[str, Any]],
    source_file: str = "",
    max_tags_per_node: int = 10
) -> list[dict[str, Any]]:
    """
    Add auto-generated tags and domain to a list of nodes.
    
    Args:
        nodes: List of node dictionaries
        source_file: Source filename for context
        max_tags_per_node: Maximum tags per node
        
    Returns:
        Nodes with tags and domain added to metadata
    """
    tagged_nodes: list[dict[str, Any]] = []
    
    for node in nodes:
        # Create a copy to avoid modifying original
        tagged_node = node.copy()
        if "metadata" not in tagged_node:
            tagged_node["metadata"] = {}
        else:
            tagged_node["metadata"] = node["metadata"].copy()
        
        content = node.get("content", "")
        
        # Generate tags
        tags = auto_tag_node(node, source_file)[:max_tags_per_node]
        tagged_node["metadata"]["tags"] = tags
        
        # Detect domain
        domain = get_primary_domain(content, source_file)
        tagged_node["metadata"]["domain"] = domain
        
        tagged_nodes.append(tagged_node)
    
    return tagged_nodes


def get_available_tags() -> list[str]:
    """
    Get list of all available tag names.
    
    Returns:
        Sorted list of tag names
    """
    return sorted(TAG_DEFINITIONS.keys())


def get_tag_keywords(tag: str) -> list[str]:
    """
    Get keywords for a specific tag.
    
    Args:
        tag: Tag name
        
    Returns:
        List of keywords or empty list if tag not found
    """
    return TAG_DEFINITIONS.get(tag, [])


if __name__ == "__main__":
    # Test with medical content
    medical_content = """
    Tim mạch là một lĩnh vực quan trọng trong y học, nghiên cứu về cấu trúc và chức năng 
    của tim và các mạch máu. Các bệnh tim mạch là nguyên nhân chính gây tử vong trên toàn thế giới.
    
    Phác đồ điều trị tăng huyết áp theo hướng dẫn của Bộ Y Tế bao gồm:
    - Thay đổi lối sống
    - Sử dụng thuốc hạ huyết áp
    - Theo dõi định kỳ
    
    Chẩn đoán bằng ECG và siêu âm tim giúp phát hiện sớm các bệnh lý tim mạch.
    """
    
    it_content = """
    Machine learning là một nhánh của trí tuệ nhân tạo (AI), cho phép máy tính học từ dữ liệu.
    Các mô hình deep learning sử dụng neural network để phân tích và xử lý thông tin.
    
    Python là ngôn ngữ lập trình phổ biến nhất cho data science và AI, với các thư viện như:
    - TensorFlow và PyTorch cho deep learning
    - Pandas và NumPy cho xử lý dữ liệu
    - Scikit-learn cho machine learning truyền thống
    
    DevOps và CI/CD giúp tự động hóa quy trình phát triển phần mềm.
    """
    
    finance_content = """
    Thị trường chứng khoán Việt Nam đã có sự tăng trưởng mạnh mẽ trong năm qua.
    VN-Index đạt mức cao kỷ lục với sự tham gia của nhiều nhà đầu tư mới.
    
    Ngân hàng nhà nước đã điều chỉnh lãi suất để kiểm soát lạm phát và thúc đẩy tăng trưởng kinh tế.
    Các doanh nghiệp fintech cũng phát triển mạnh với ví điện tử và thanh toán số.
    """
    
    print("=" * 70)
    print("AUTO-TAGGING TEST - Multiple Domains")
    print("=" * 70)
    
    # Test 1: Medical
    print("\n📋 TEST 1: Y Học Content")
    print("-" * 50)
    domain = get_primary_domain(medical_content, "Harrison_Tim_Mach.pdf")
    tags = auto_tag_content(medical_content, "Giới thiệu về Y Học Tim Mạch", "Harrison_Tim_Mach.pdf")
    print(f"Domain: {domain}")
    print(f"Tags: {tags}")
    
    # Test 2: IT
    print("\n💻 TEST 2: CNTT Content")
    print("-" * 50)
    domain = get_primary_domain(it_content, "AI_Machine_Learning.pdf")
    tags = auto_tag_content(it_content, "Machine Learning và AI", "AI_Machine_Learning.pdf")
    print(f"Domain: {domain}")
    print(f"Tags: {tags}")
    
    # Test 3: Finance
    print("\n💰 TEST 3: Kinh tế - Tài chính Content")
    print("-" * 50)
    domain = get_primary_domain(finance_content, "Bao_cao_tai_chinh.pdf")
    tags = auto_tag_content(finance_content, "Thị trường tài chính", "Bao_cao_tai_chinh.pdf")
    print(f"Domain: {domain}")
    print(f"Tags: {tags}")
    
    # Statistics
    print("\n📊 STATISTICS")
    print("-" * 50)
    print(f"Total available tags: {len(get_available_tags())}")
    print(f"Total domains: {len(DOMAIN_DEFINITIONS)}")
    print(f"Domains: {list(DOMAIN_DEFINITIONS.keys())}")
