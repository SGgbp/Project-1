// SnapReply — minimal dashboard JS
// Currently handles billing toggle and referral tracking

// Track referral source from viral footer URL
const urlParams = new URLSearchParams(window.location.search);
const ref = urlParams.get('ref');
if (ref) {
  sessionStorage.setItem('snapreply_ref', ref);
}

// Append referral code to all register links if present
document.addEventListener('DOMContentLoaded', () => {
  const storedRef = sessionStorage.getItem('snapreply_ref');
  if (storedRef) {
    document.querySelectorAll('a[href*="/api/auth/register"]').forEach(link => {
      const url = new URL(link.href, window.location.origin);
      url.searchParams.set('ref', storedRef);
      link.href = url.toString();
    });
  }
});
