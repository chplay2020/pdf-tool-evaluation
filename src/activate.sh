#!/bin/bash
# Quick Start Script - Activate virtual environment
# ==================================================
# Sử dụng: source activate.sh

echo "🚀 Activating virtual environment..."
source venv_marker/bin/activate

echo "✅ Virtual environment activated!"
echo ""
echo "📋 Quick Commands:"
echo "  python main_pipeline.py --list                    # Xem danh sách PDF"
echo "  python main_pipeline.py <filename.pdf>            # Chạy pipeline"
echo "  python main_pipeline.py <filename.pdf> --save-intermediate  # Debug mode"
echo ""
echo "💡 Example:"
echo "  python main_pipeline.py test_simple_2.pdf"
echo ""
