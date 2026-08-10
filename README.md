# AI-Powered Predictive Hypertension Management Ecosystem

## Project structure

- backend/
  - src/
    - controllers/
    - routes/
    - models/
    - services/
    - utils/
    - middleware/
  - tests/

- frontend/
  - web/
    - src/
      - components/
      - pages/
      - services/
      - styles/
      - assets/
    - public/
    - tests/
  - mobile/
    - lib/
    - src/
      - screens/
      - widgets/
      - services/
    - assets/

- ai/
  - component1-physiological/
    - data/
    - notebooks/
    - models/
    - src/
    - tests/
  - component2-behavioral/
    - data/
    - notebooks/
    - models/
    - src/
    - tests/
  - component3-nutrition/
    - data/
    - notebooks/
    - models/
    - src/
    - tests/
  - component4-medicine/
    - data/
    - notebooks/
    - models/
    - src/
    - tests/
  - common/
    - data/
    - utils/

- data/
  - raw/
  - processed/
  - external/

- docs/
- infra/
  - docker/
  - k8s/
- scripts/
- tests/

## Notes

This structure supports a modular ecosystem with separated backend, frontend, AI research components, data stores, documentation, and deployment infrastructure.

## Getting Started

- Backend:
  - `cd backend`
  - `npm install`
  - `npm run dev`

- Frontend Web:
  - `cd frontend/web`
  - `npm install`
  - `npm start`

- AI prototyping:
  - `cd ai`
  - `python -m venv venv`
  - `venv\Scripts\activate`
  - `pip install -r requirements.txt`

- Mobile App:
  - `cd frontend/mobile`
  - `flutter pub get`

> Use the generated folders as the base for each component and expand them with services, dashboards, models, and datasets as needed.
