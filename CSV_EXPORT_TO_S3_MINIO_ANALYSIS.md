# Superset CSV导出到S3/MinIO功能分析报告

## 概述
本文档详细分析了Apache Superset中CSV导出功能，以及是否支持将报表文件导出到MinIO或S3存储，并提供可能的扩展点建议。

## 现有功能分析

### 1. CSV导出功能

Superset目前支持以下CSV导出方式：

#### 1.1 流式CSV导出（Streaming CSV Export）
位置: `superset/commands/streaming_export/`

- **SQL Lab查询结果导出**
  - 文件: `superset/commands/sql_lab/streaming_export_command.py`
  - 功能: 将SQL Lab查询结果导出为CSV
  - 实现: 使用流式处理，分块读取和写入数据
  - 返回: 直接返回CSV数据流给客户端（HTTP响应）

- **图表数据导出**
  - 文件: `superset/commands/chart/data/streaming_export_command.py`
  - 功能: 将图表数据导出为CSV
  - 实现: 基于QueryContext生成SQL并导出
  - 返回: 直接返回CSV数据流给客户端

#### 1.2 报表/告警CSV导出
位置: `superset/commands/report/execute.py`

- **功能**: 定期生成报表并通过通知渠道发送
- **支持格式**: PNG, CSV, TEXT
- **实现方式**:
  ```python
  def _get_csv_data(self) -> bytes:
      # 获取图表URL
      url = self._get_url(result_format=ChartDataResultFormat.CSV)
      # 通过HTTP请求获取CSV数据
      csv_data = get_chart_csv_data(chart_url=url, auth_cookies=auth_cookies)
      return csv_data
  ```
- **通知渠道**: 
  - Email (带附件)
  - Slack
  - Webhook
  - 等等

### 2. S3/MinIO相关功能

目前Superset在以下场景中支持S3/MinIO：

#### 2.1 查询结果后端存储（RESULTS_BACKEND）
位置: `superset/config.py:1356`

**配置示例**:
```python
# S3作为查询结果后端
from s3cache.s3cache import S3Cache
S3_CACHE_BUCKET = 'foobar-superset'
S3_CACHE_KEY_PREFIX = 'sql_lab_result'
RESULTS_BACKEND = S3Cache(S3_CACHE_BUCKET, S3_CACHE_KEY_PREFIX)
```

**用途**:
- 存储SQL Lab异步查询的结果
- 存储大型查询结果，避免超时
- 需要配置Celery worker

**文档位置**: 
- `docs/docs/configuration/async-queries-celery.mdx`
- `docs/docs/configuration/cache.mdx`

#### 2.2 缩略图缓存（Thumbnail Cache）
位置: `docs/docs/configuration/cache.mdx:106-132`

**配置示例**:
```python
from s3cache.s3cache import S3Cache

def init_thumbnail_cache(app: Flask) -> S3Cache:
    return S3Cache("bucket_name", 'thumbs_cache/')

THUMBNAIL_CACHE_CONFIG = init_thumbnail_cache
```

**用途**:
- 存储仪表板和图表的缩略图
- 提高加载速度

### 3. 当前CSV导出的存储方式

**重要发现**: 目前Superset的CSV导出功能**不直接支持**将CSV文件自动保存到S3/MinIO。

现有实现方式：

1. **流式导出（用户手动下载）**:
   - 数据直接通过HTTP响应流返回给客户端
   - 用户浏览器接收并保存文件
   - 不涉及服务器端文件存储

2. **报表/告警CSV导出**:
   - CSV数据作为附件通过Email发送
   - 或通过Webhook以文件形式POST出去
   - 数据存在于内存中，不持久化到文件系统或对象存储

## 扩展点分析

虽然Superset目前不直接支持将CSV报表文件导出到MinIO/S3，但提供了多个扩展点：

### 扩展点1: 自定义通知类型（Notification Plugin）

**位置**: `superset/reports/notifications/`

**实现方式**:
```python
# 创建自定义S3通知类
from superset.reports.notifications.base import BaseNotification

class S3Notification(BaseNotification):
    """
    将报表CSV文件上传到S3/MinIO
    """
    type = "s3"
    
    def send(self) -> None:
        # 实现S3上传逻辑
        import boto3
        s3_client = boto3.client('s3')
        
        if self._content.csv:
            # 上传CSV到S3
            s3_client.put_object(
                Bucket='your-bucket',
                Key=f'reports/{self._report_schedule.id}/{datetime.now()}.csv',
                Body=self._content.csv
            )
```

**优点**:
- 符合Superset插件架构
- 可以与现有报表调度系统集成
- 支持定期自动导出

**注册方式**:
在 `superset/reports/notifications/__init__.py` 中注册新的通知类型

### 扩展点2: 自定义Webhook处理器

**位置**: `superset/reports/notifications/webhook.py`

**实现方式**:
配置一个webhook端点，接收CSV数据并上传到S3/MinIO：

```python
# webhook配置
RECIPIENT_CONFIG_JSON = {
    "target": "https://your-service.com/upload-to-s3",
    "headers": {
        "Authorization": "Bearer token"
    }
}
```

在webhook服务中：
```python
# webhook服务接收CSV并上传到S3
@app.post('/upload-to-s3')
def upload_to_s3():
    csv_file = request.files['files']
    # 上传到S3/MinIO
    s3_client.upload_fileobj(csv_file, 'bucket-name', 'key')
```

**优点**:
- 无需修改Superset代码
- 灵活，可以添加自定义逻辑
- 与现有Webhook功能兼容

### 扩展点3: 修改流式导出命令

**位置**: `superset/commands/streaming_export/base.py`

**实现方式**:
扩展 `BaseStreamingCSVExportCommand` 类：

```python
class S3StreamingCSVExportCommand(BaseStreamingCSVExportCommand):
    """
    导出CSV并同时保存到S3
    """
    def run(self):
        # 获取CSV生成器
        csv_generator = super().run()
        
        # 同时保存到S3
        import boto3
        s3_client = boto3.client('s3')
        
        # 收集所有CSV数据
        csv_data = b''.join(chunk.encode('utf-8') for chunk in csv_generator())
        
        # 上传到S3
        s3_client.put_object(
            Bucket='bucket-name',
            Key=f'exports/{timestamp}.csv',
            Body=csv_data
        )
        
        # 返回生成器供HTTP响应使用
        return lambda: (chunk for chunk in [csv_data.decode('utf-8')])
```

**优点**:
- 可以同时支持下载和S3存储
- 集成在导出流程中

**缺点**:
- 需要修改核心代码
- 需要将整个CSV加载到内存

### 扩展点4: Celery任务扩展

**位置**: `superset/tasks/`

**实现方式**:
创建自定义Celery任务：

```python
# superset/tasks/s3_export.py
from celery import Task
from superset.tasks.celery_app import app

@app.task
def export_chart_to_s3(chart_id: int, s3_bucket: str, s3_key: str):
    """
    异步导出图表数据到S3
    """
    # 1. 获取图表数据
    # 2. 生成CSV
    # 3. 上传到S3
    import boto3
    s3_client = boto3.client('s3')
    
    # ... 实现逻辑
    s3_client.put_object(Bucket=s3_bucket, Key=s3_key, Body=csv_data)
```

**优点**:
- 异步处理，不阻塞用户请求
- 可以处理大型数据集
- 可以配置定期任务

## MinIO支持

MinIO完全兼容S3 API，因此所有S3相关的扩展都可以直接用于MinIO：

```python
# 配置MinIO客户端
import boto3

s3_client = boto3.client(
    's3',
    endpoint_url='http://minio-server:9000',  # MinIO端点
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
    region_name='us-east-1'
)

# 使用方式与S3完全相同
s3_client.put_object(
    Bucket='reports',
    Key='export.csv',
    Body=csv_data
)
```

## 推荐实现方案

### 方案1: 自定义通知插件（推荐用于报表/告警）

**适用场景**: 需要定期自动将报表CSV导出到S3/MinIO

**实现步骤**:

1. 创建 `superset/reports/notifications/s3.py`:
```python
from typing import Optional
import boto3
from datetime import datetime
from superset.reports.notifications.base import BaseNotification
from superset.reports.notifications.exceptions import NotificationError

class S3Notification(BaseNotification):
    """
    将报表CSV文件上传到S3/MinIO
    """
    type = "s3"
    
    def _get_s3_config(self) -> dict:
        """从recipient_config_json获取S3配置"""
        import json
        config = json.loads(self._recipient.recipient_config_json)
        return {
            'bucket': config.get('bucket'),
            'prefix': config.get('prefix', 'reports/'),
            'endpoint_url': config.get('endpoint_url'),  # MinIO endpoint
            'aws_access_key_id': config.get('aws_access_key_id'),
            'aws_secret_access_key': config.get('aws_secret_access_key'),
        }
    
    def send(self) -> None:
        try:
            s3_config = self._get_s3_config()
            
            # 创建S3客户端
            s3_client = boto3.client(
                's3',
                endpoint_url=s3_config.get('endpoint_url'),
                aws_access_key_id=s3_config['aws_access_key_id'],
                aws_secret_access_key=s3_config['aws_secret_access_key'],
            )
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{s3_config['prefix']}{self._content.name}_{timestamp}.csv"
            
            # 上传CSV到S3/MinIO
            if self._content.csv:
                s3_client.put_object(
                    Bucket=s3_config['bucket'],
                    Key=filename,
                    Body=self._content.csv,
                    ContentType='text/csv'
                )
                logger.info(f"Report CSV uploaded to s3://{s3_config['bucket']}/{filename}")
        except Exception as ex:
            raise NotificationError(f"Failed to upload to S3: {str(ex)}") from ex
```

2. 在 `superset/reports/notifications/__init__.py` 中注册:
```python
from superset.reports.notifications.s3 import S3Notification  # noqa: F401
```

3. 在数据库中添加S3类型的接收者:
```sql
INSERT INTO report_recipient (
    type, recipient_config_json, report_schedule_id
) VALUES (
    's3',
    '{"bucket": "my-bucket", "prefix": "reports/", "endpoint_url": "http://minio:9000", "aws_access_key_id": "...", "aws_secret_access_key": "..."}',
    <report_schedule_id>
);
```

### 方案2: Webhook + 中间服务（推荐用于简单场景）

**适用场景**: 不想修改Superset代码，通过外部服务处理

**实现步骤**:

1. 创建独立的webhook服务:
```python
# webhook_to_s3.py
from flask import Flask, request
import boto3

app = Flask(__name__)

@app.route('/upload-report', methods=['POST'])
def upload_report():
    # 获取CSV文件
    csv_file = request.files.get('files')
    
    # 上传到S3/MinIO
    s3_client = boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
    )
    
    filename = f"reports/{request.form.get('name', 'report')}.csv"
    s3_client.upload_fileobj(csv_file, 'reports-bucket', filename)
    
    return {'status': 'success', 'file': filename}
```

2. 在Superset中配置Webhook接收者:
```json
{
  "target": "http://webhook-service:5000/upload-report"
}
```

## 依赖包

需要安装的Python包：

```bash
# S3支持
pip install boto3

# S3 Cache（用于RESULTS_BACKEND）
pip install s3-cache-backend
# 或
pip install s3werkzeugcache
```

MinIO配置示例：
```python
# superset_config.py
import boto3

# MinIO配置
MINIO_ENDPOINT = 'http://minio:9000'
MINIO_ACCESS_KEY = 'minioadmin'
MINIO_SECRET_KEY = 'minioadmin'
MINIO_BUCKET = 'superset-reports'
```

## 总结

### 现有功能
- ✅ Superset支持CSV导出（流式下载、报表附件）
- ✅ Superset支持S3/MinIO作为查询结果缓存（RESULTS_BACKEND）
- ✅ Superset支持S3/MinIO作为缩略图缓存
- ❌ Superset **不直接支持**将报表CSV文件自动保存到S3/MinIO

### 扩展方案
1. **自定义通知插件**（推荐）- 与报表系统深度集成
2. **Webhook + 中间服务** - 简单快速，无需修改代码
3. **修改流式导出命令** - 适合需要双向支持的场景
4. **Celery任务** - 适合复杂的后台处理需求

### 推荐方案
对于大多数场景，建议使用**自定义通知插件**方案（方案1），因为：
- 与Superset报表调度系统无缝集成
- 支持定期自动导出
- 代码结构清晰，易于维护
- 完全符合Superset插件架构

如果只是临时需求或快速验证，可以使用**Webhook + 中间服务**方案（方案2）。

## 参考文档

- Superset异步查询配置: `docs/docs/configuration/async-queries-celery.mdx`
- 缓存配置: `docs/docs/configuration/cache.mdx`
- 报表通知基类: `superset/reports/notifications/base.py`
- CSV导出实现: `superset/utils/csv.py`
- 流式导出命令: `superset/commands/streaming_export/`
