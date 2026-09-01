type ReviewPackage = {
  status: string;
  spec_hash: string | null;
  artifact_hash: string | null;
  sandbox_report_hash: string | null;
};

export type StrategyDraftReview = {
  label: string;
  detail: string;
  canApprove: boolean;
};

export function strategyDraftReview(draft: ReviewPackage | null): StrategyDraftReview {
  if (!draft) {
    return {
      label: "Chưa tạo draft",
      detail: "Nhập mô tả hoặc URL đã được phép để tạo package review.",
      canApprove: false,
    };
  }

  const completePackage = Boolean(draft.spec_hash && draft.artifact_hash && draft.sandbox_report_hash);
  if (draft.status === "REVIEW_REQUIRED" && completePackage) {
    return {
      label: "Sẵn sàng phê duyệt",
      detail: "Spec, artifact và preflight report đã được cố định bằng fingerprint.",
      canApprove: true,
    };
  }
  if (draft.status === "APPROVED") {
    return {
      label: "Đã lưu vào Strategy Library",
      detail: "Version đã publish giữ nguyên fingerprint đã duyệt.",
      canApprove: false,
    };
  }
  if (draft.status === "REJECTED" || draft.status === "FAILED") {
    return {
      label: draft.status === "REJECTED" ? "Draft đã bị từ chối" : "Tạo draft thất bại",
      detail: "Tạo draft mới sau khi điều chỉnh mô tả hoặc dữ liệu nguồn.",
      canApprove: false,
    };
  }
  return {
    label: "Đang chuẩn bị review package",
    detail: "Đợi hệ thống hoàn tất validation và preflight trước khi phê duyệt.",
    canApprove: false,
  };
}
