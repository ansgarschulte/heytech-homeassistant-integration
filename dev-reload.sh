#!/bin/bash
# Quick reload script for Heytech integration development

set -e

CONTAINER="homeassistant-heytech-test"

echo "🔄 Heytech Integration Reload"
echo "=============================="

# Check if container is running
if ! docker ps | grep -q $CONTAINER; then
    echo "❌ Container not running. Start it with: docker-compose up -d"
    exit 1
fi

echo "✅ Container is running"
echo ""

# Show what changed
echo "📝 Recent file changes:"
git status -s custom_components/heytech/ 2>/dev/null || echo "  (Git not available)"
echo ""

# Ask for reload type
echo "Choose reload method:"
echo "1) Quick reload (fast, recommended)"
echo "2) Full restart (slow, but thorough)"
echo "3) Just show logs"
echo ""
read -p "Choice [1]: " choice
choice=${choice:-1}

case $choice in
    1)
        echo ""
        echo "🔄 Quick reloading Home Assistant core..."
        docker exec $CONTAINER ha core reload
        echo "✅ Quick reload completed!"
        ;;
    2)
        echo ""
        echo "🔄 Restarting container..."
        docker-compose restart
        echo "✅ Container restarted!"
        ;;
    3)
        echo ""
        echo "📋 Showing logs (press Ctrl+C to stop)..."
        docker-compose logs -f homeassistant | grep -i heytech
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "📋 Showing recent logs..."
docker-compose logs --tail=30 homeassistant | grep -i heytech || echo "  (No heytech logs yet)"

echo ""
echo "✅ Done! Check http://localhost:8123"
