SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS vector_mapping;
DROP TABLE IF EXISTS job_text;
DROP TABLE IF EXISTS job_post;
DROP TABLE IF EXISTS raw_document;
DROP TABLE IF EXISTS company;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE company (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '企业主键ID',
    company_name VARCHAR(100) NOT NULL COMMENT '企业标准名称',
    company_alias VARCHAR(100) DEFAULT NULL COMMENT '企业别名或简称',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_company_name (company_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业信息表';

CREATE TABLE raw_document (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '原始文档主键ID',
    company_name VARCHAR(100) NOT NULL COMMENT '企业名称',
    source_url VARCHAR(500) NOT NULL COMMENT '原始页面链接',
    content_type VARCHAR(50) NOT NULL COMMENT '内容类型：html/json',
    html_content LONGTEXT COMMENT '原始HTML内容',
    json_content LONGTEXT COMMENT '原始JSON内容',
    checksum VARCHAR(64) DEFAULT NULL COMMENT '原始内容校验哈希',
    fetched_at DATETIME NOT NULL COMMENT '抓取时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_company_name (company_name),
    KEY idx_source_url (source_url(255)),
    KEY idx_fetched_at (fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始抓取文档表';


CREATE TABLE job_post (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '岗位主键ID',
    company_id BIGINT NOT NULL COMMENT '企业ID',
    source_url VARCHAR(500) NOT NULL COMMENT '岗位原始链接',
    job_title VARCHAR(255) NOT NULL COMMENT '职位名称',
    product_line VARCHAR(255) DEFAULT NULL COMMENT '产品线',
    job_location VARCHAR(255) DEFAULT NULL COMMENT '工作地点',
    crawl_time DATETIME NOT NULL COMMENT '抓取时间',
    status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '岗位状态：active/inactive',
    raw_doc_id BIGINT DEFAULT NULL COMMENT '关联原始文档ID',
    raw_text_hash VARCHAR(64) DEFAULT NULL COMMENT '岗位文本内容哈希值',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    CONSTRAINT fk_job_post_company FOREIGN KEY (company_id) REFERENCES company(id),
    UNIQUE KEY uk_source_url (source_url),
    KEY idx_company_id (company_id),
    KEY idx_job_title (job_title),
    KEY idx_product_line (product_line),
    KEY idx_job_location (job_location),
    KEY idx_crawl_time (crawl_time),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='招聘岗位主表';


CREATE TABLE job_text (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '岗位文本主键ID',
    job_post_id BIGINT NOT NULL COMMENT '岗位ID',
    job_requirement TEXT COMMENT '原始招聘要求',
    job_responsibility TEXT COMMENT '原始岗位职责',
    cleaned_requirement TEXT COMMENT '清洗后的招聘要求',
    cleaned_responsibility TEXT COMMENT '清洗后的岗位职责',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    CONSTRAINT fk_job_text_post FOREIGN KEY (job_post_id) REFERENCES job_post(id),
    UNIQUE KEY uk_job_post_id (job_post_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位文本信息表';


CREATE TABLE vector_mapping (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '向量映射主键ID',
    job_post_id BIGINT NOT NULL COMMENT '岗位ID',
    vector_doc_id VARCHAR(128) NOT NULL COMMENT '向量库文档ID',
    text_type VARCHAR(50) NOT NULL COMMENT '文本类型：requirement/responsibility',
    chunk_count INT NOT NULL DEFAULT 0 COMMENT '切块数量',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    CONSTRAINT fk_vector_mapping_post FOREIGN KEY (job_post_id) REFERENCES job_post(id),
    KEY idx_job_post_id (job_post_id),
    KEY idx_vector_doc_id (vector_doc_id),
    KEY idx_text_type (text_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位与向量文档映射表';