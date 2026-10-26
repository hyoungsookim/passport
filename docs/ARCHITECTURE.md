## 1. 확정된 아키텍처 결정

| 주제            | 결정 사항                                                    |
| --------------- | ------------------------------------------------------------ |
| 서비스명        | **Passport**                                                 |
| 서비스 성격     | 중앙 Identity / Authentication / Account / Global Tenant Management |
| 인증 방식       | External OIDC + Local Authentication                         |
| 인증 추상화     | 추상 `Authentication` 클래스를 공통 계약으로 정의하고 Local·OIDC 구현이 이를 상속. 향후 SAML 구현도 같은 계약으로 추가하며, 인증 결과는 공통 내부 인증 정보로 제공. SAML 자체 구현은 향후 범위. |
| 외부 OIDC 토큰  | 외부 Provider가 발급한 토큰을 Passport 자체 토큰으로 교환·재발급하지 않고 사용. |
| 자체 인증 토큰  | Local Authentication을 통해 Passport가 RFC 9068을 따르는 JWT Access Token을 발급할 수 있음. 별도의 신원 정보 전달용 JWT 또는 OIDC ID Token은 발급하지 않으며, 사용자 정보는 인증된 API로 조회. |
| JWT 검증 공통화 | Local Access Token과 외부 JWT Access Token은 발급자·테넌트별 검증 설정과 클레임 매핑을 적용하는 동일한 검증 엔진에서 처리. |
| 내부 인증 정보  | 검증 결과는 원본 발급자·Passport 사용자 신원·인증 방식·테넌트 인증 범위를 보존하는 공통 내부 인증 정보로 변환하여 사용. 외부 토큰의 재발급·교환은 수행하지 않음. |
| 프로토콜상 역할 | Passport를 **OIDC Provider** 또는 **OAuth2 Authorization Server**로 정의하지 않음. |
| 개인정보        | Passport가 공통 가입자의 개인정보를 저장·관리.                |
| 계정 생명주기   | 가입, 비밀번호 변경, 계정 변경 및 탈퇴 등을 Passport가 담당.  |
| 테넌트 모델     | **Global Tenant 단일 모델**                                  |
| 테넌트 소유권   | Passport가 전역 테넌트의 생성·관리 및 식별자 소유.            |
| 테넌트 식별자   | 모든 연동 SaaS가 공통 `tenant_id` 사용.                       |
| 서비스별 테넌트 | **도입하지 않음** (`ApplicationTenant` 및 Hybrid Tenant 구조 제외) |
| SaaS 책임       | 각 SaaS는 자신의 도메인 데이터, 워크스페이스·공간 및 세부 리소스 접근 정책을 관리. |
| 사용자 접근     | 전역 테넌트 소속과 SaaS 이용 자격, SaaS 내부 리소스 권한을 구분. |

## 