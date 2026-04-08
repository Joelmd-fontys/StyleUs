API_DIR := services/api
WEB_DIR := apps/web

.PHONY: dev db-up db-down run worker worker-service lint test typecheck benchmark-category review-feedback-report review-feedback-export

dev:
	./dev.sh

db-up:
	$(MAKE) -C $(API_DIR) db-up

db-down:
	$(MAKE) -C $(API_DIR) db-down

run:
	$(MAKE) -C $(API_DIR) run

worker:
	$(MAKE) -C $(API_DIR) worker

worker-service:
	$(MAKE) -C $(API_DIR) worker-service

lint:
	$(MAKE) -C $(API_DIR) lint
	cd $(WEB_DIR) && npm run lint

test:
	$(MAKE) -C $(API_DIR) test
	cd $(WEB_DIR) && npm test

benchmark-category:
	$(MAKE) -C $(API_DIR) benchmark-category

review-feedback-report:
	$(MAKE) -C $(API_DIR) review-feedback-report

review-feedback-export:
	$(MAKE) -C $(API_DIR) review-feedback-export

typecheck:
	$(MAKE) -C $(API_DIR) typecheck
	cd $(WEB_DIR) && npm run typecheck
