# ================================================
# services/pdf_generation/pdf_charts.py
# 📈 رسم الرسوم البيانية الاحترافية
# ================================================

import logging
import io
from typing import Dict, List, Any, Optional
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

logger = logging.getLogger(__name__)


class ChartRenderer:
    """رسم الرسوم البيانية الاحترافية والموحدة"""
    
    # إعدادات Matplotlib الموحدة
    COLORS = [
        '#1565C0',  # أزرق
        '#0288D1',  # أزرق فاتح
        '#2E7D32',  # أخضر
        '#F57F17',  # برتقالي
        '#C62828',  # أحمر
        '#6A1B9A',  # بنفسجي
        '#00838F',  # تركواز
        '#E65100',  # برتقالي داكن
    ]
    
    @staticmethod
    def setup_arabic_matplotlib():
        """إعداد Matplotlib للعربية"""
        rcParams['font.family'] = 'DejaVu Sans'
        rcParams['axes.unicode_minus'] = False
    
    @classmethod
    def create_bar_chart(
        cls,
        labels: List[str],
        values: List[float],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        horizontal: bool = False,
    ) -> io.BytesIO:
        """
        إنشاء رسم بياني عمودي/أفقي
        
        Args:
            labels: تسميات البيانات
            values: القيم
            title: عنوان الرسم
            xlabel: تسمية المحور الأفقي
            ylabel: تسمية المحور العمودي
            horizontal: هل الرسم أفقي؟
            
        Returns:
            BytesIO object
        """
        
        logger.info(f"📊 إنشاء رسم بياني عمودي: {title}")
        
        cls.setup_arabic_matplotlib()
        
        fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
        
        if horizontal:
            ax.barh(labels, values, color=cls.COLORS[:len(labels)])
        else:
            ax.bar(labels, values, color=cls.COLORS[:len(labels)])
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        
        # تدوير التسميات إذا لزم الأمر
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # حفظ إلى BytesIO
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        logger.info(f"✅ تم إنشاء الرسم البياني بنجاح")
        return buffer
    
    @classmethod
    def create_pie_chart(
        cls,
        labels: List[str],
        values: List[float],
        title: str = "",
    ) -> io.BytesIO:
        """
        إنشاء رسم دائري
        
        Args:
            labels: تسميات البيانات
            values: القيم
            title: عنوان الرسم
            
        Returns:
            BytesIO object
        """
        
        logger.info(f"📊 إنشاء رسم دائري: {title}")
        
        cls.setup_arabic_matplotlib()
        
        fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
        
        # عرض أعلى 5 عناصر فقط (الباقي "أخرى")
        if len(labels) > 5:
            top_5_indices = sorted(range(len(values)), key=lambda i: values[i], reverse=True)[:5]
            labels_pie = [labels[i] for i in top_5_indices]
            values_pie = [values[i] for i in top_5_indices]
            
            # أضف "أخرى"
            other_value = sum(values) - sum(values_pie)
            labels_pie.append("أخرى")
            values_pie.append(other_value)
        else:
            labels_pie = labels
            values_pie = values
        
        ax.pie(
            values_pie,
            labels=labels_pie,
            autopct='%1.1f%%',
            colors=cls.COLORS[:len(labels_pie)],
            startangle=90,
        )
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        # حفظ إلى BytesIO
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        logger.info(f"✅ تم إنشاء الرسم الدائري بنجاح")
        return buffer
    
    @classmethod
    def create_line_chart(
        cls,
        x_data: List[str],
        y_data: List[float],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
    ) -> io.BytesIO:
        """
        إنشاء رسم خطي
        
        Args:
            x_data: بيانات المحور الأفقي
            y_data: بيانات المحور العمودي
            title: عنوان الرسم
            xlabel: تسمية المحور الأفقي
            ylabel: تسمية المحور العمودي
            
        Returns:
            BytesIO object
        """
        
        logger.info(f"📊 إنشاء رسم خطي: {title}")
        
        cls.setup_arabic_matplotlib()
        
        fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
        
        ax.plot(x_data, y_data, marker='o', linewidth=2, markersize=6, color='#1565C0')
        ax.fill_between(range(len(x_data)), y_data, alpha=0.3, color='#0288D1')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        
        # شبكة
        ax.grid(True, alpha=0.3)
        
        # تدوير التسميات
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # حفظ إلى BytesIO
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        logger.info(f"✅ تم إنشاء الرسم الخطي بنجاح")
        return buffer
