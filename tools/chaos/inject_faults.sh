#!/bin/bash

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Initializing Chaos Engineering Suite ${NC}\n"

case "$1" in
  "test-a")
    echo -e "${YELLOW}Executing Test A: The Outbox Drop${NC}"
    echo "Start your Locust test now to generate load on API"
    read -p "Press Enter when Locust is actively firing..."
    
    echo -e "${RED}Killing outbox_publisher container...${NC}"
    docker compose stop outbox_publisher
    
    echo -e "${CYAN}Container is dead. API is still accepting traffic.${NC}"
    echo "Postgres 'outbox' table is silently filling up..."
    
    # Wait for 60 seconds to simulate a prolonged outage and allow the outbox to accumulate
    for i in {60..1}; do
        echo -ne "Waiting $i seconds to restore...\r"
        sleep 1
    done
    echo ""

    echo -e "${GREEN}Restoring outbox_publisher...${NC}"
    docker compose start outbox_publisher
    echo -e "Test Complete. Watch your Redpanda logs to see the outbox drain.\n"
    ;;

  "test-b")
    echo -e "${YELLOW}Executing Test B: Redis Volatility${NC}"
    echo -e "${RED}Sending SIGKILL to Redis container...${NC}"
    # Using 'kill' to simulate hard crash instead of a graceful shutdown
    docker compose kill redis 
    
    echo -e "${CYAN}Redis is dead. Scheduler workers will start throwing connection errors.${NC}"
    sleep 10
    
    echo -e "${GREEN}Rebooting Redis (Blank State)...${NC}"
    docker compose start redis
    sleep 5
    
    echo -e "Redis restored. Fetching Scheduler logs to verify Bootstrapper recovery:"
    echo -e "${CYAN}--------------------------------------------------${NC}"
    docker logs --tail 20 $(docker compose ps -q scheduler_worker)
    echo -e "${CYAN}--------------------------------------------------${NC}"
    echo -e "Look for the log: 'Successfully connected... Bootstrap complete.'\n"
    ;;

  "test-c")
    echo -e "${YELLOW}Executing Test C: Upstream Provider 503 Outage${NC}"
    echo "To simulate this without altering code, dynamically inject a Chaos Environment Variable."
    
    echo -e "${RED}Injecting CHAOS_MODE=503 into sms_worker...${NC}"
    # Recreate container with bad environment variable
    docker compose run -d --name chaos_sms_worker -e CHAOS_MODE="503" sms_worker
    
    echo -e "${CYAN}sms_worker is now failing all requests and routing to DLQ.${NC}"
    echo "Check the worker logs to verify Circuit Breaker trips:"
    sleep 5
    docker logs --tail 10 chaos_sms_worker
    
    read -p "Press Enter to resolve the outage..."
    
    echo -e "${GREEN}Removing Chaos Worker and restoring normal pool...${NC}"
    docker rm -f chaos_sms_worker
    echo -e "Test Complete. Un-sendable messages should be safely in the Dead Letter Queue.\n"
    ;;

  *)
    echo "Usage: ./inject_faults.sh [test-a | test-b | test-c]"
    echo "  test-a : Kills the Outbox Publisher mid-flight."
    echo "  test-b : Hard crashes Redis to test state recovery."
    echo "  test-c : Injects 503 errors into the SMS worker to test the Circuit Breaker."
    ;;
esac