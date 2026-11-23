# Dataset, Docker & Evaluation — trạng thái bàn giao

Ngày kiểm tra gần nhất: 2026-11-24 (Asia/Ho_Chi_Minh).

| Mốc | Trạng thái | Bằng chứng / giới hạn |
| --- | --- | --- |
| Mốc 1 — khảo sát | COMPLETE | NYU tag/commit, dev 57, pilot và framework được ghi trong `docs/dataset-setup.md`. |
| Mốc 2A — setup/catalog | COMPLETE | Manifest public ba pilot, tag/commit pin, Python/`nyuctf` import đã xác minh. Full checkout Windows không giữ lại. |
| Mốc 2B — Docker smoke | BLOCKED | Docker Linux Engine pipe không tồn tại; WSL2 trả `E_ACCESSDENIED`. Không pull/build/start server. |
| Mốc 2C — contract an toàn | PARTIAL | Public catalog, unavailable-safe runtime contract và owned-resource registry có unit test. Backend NYU runtime thật chờ Docker/WSL2 và private checkout. |
| Mốc 3 — evaluation | PARTIAL | Exact checker API, normalizer/redaction, metrics, export có unit test tổng hợp. Chưa có baseline/Agent/LLM/real challenge run. |

## Bằng chứng runtime hiện tại

- Branch phát triển: `feature/evaluation`.
- Dataset pin: `v20250206`, commit
  `1dc13a0dc41a71504f727649679e2b5a6d0cb1b1`.
- Docker CLI: `29.9.3`; Compose: `v5.7.0`.
- Free storage observed by a read-only check: C: about 11.35 GiB; D: about
  102.86 GiB. These are observations, not a reservation for Docker/WSL.
- Docker engine check: `open //./pipe/dockerDesktopLinuxEngine: The system
  cannot find the file specified`.
- WSL check: `Wsl/EnumerateDistros/Service/E_ACCESSDENIED`.

Không suy diễn lại lỗi Mốc 2A `permission denied`: kết quả Mốc 2B mới là pipe
không tồn tại, còn WSL vẫn access denied. Vị trí Docker disk image và distro
chưa thể xác minh qua daemon/WSL nên là `not_available`, không đoán vị trí.

## Điều kiện tiếp tục

1. Chủ máy cho phép và hoàn tất việc khôi phục quyền WSL2/Docker Desktop Linux
   Engine. Không tự sửa service, registry, ACL, WSL installation hay Docker
   Desktop setting từ module này.
2. Chủ máy phê duyệt vị trí storage Docker/WSL trên D: và dung lượng headroom
   trước image pull/build. Không tự move VHDX/image/volume hay prune.
3. Sau khi WSL hoạt động, clone NYU vào Linux filesystem (ví dụ `~/ctf-data`),
   không phải NTFS mount, rồi verify commit pin.
4. Smoke test theo thứ tự Sleeping Guard rồi WarmUp, mỗi run cleanup resource
   module-owned và lưu log redact.
5. Baseline/LLM thật chỉ sau khi owner phê duyệt provider, API key handling,
   model và giới hạn chi phí/thời gian. Report phải ghi version/model và trạng
   thái verified/unverified.
