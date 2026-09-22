/* anchor 시험용 C 표본. 커널 파일시스템 GC의 모양만 흉내낸 것이고 실제 코드가 아니다.
 * 커널 C 관례(0열 여는 중괄호, static 함수)를 그대로 따라야 brace scan을 시험할 수 있다.
 */
#include <linux/kernel.h>

static int victim_zone(struct zone_sb_info *sbi, unsigned int *out)
{
	unsigned int i, best = UINT_MAX;

	for (i = 0; i < sbi->nr_zones; i++) {
		if (sbi->zone[i].valid_blocks < best) {
			best = sbi->zone[i].valid_blocks;
			*out = i;
		}
	}
	return best == UINT_MAX ? -ENOSPC : 0;
}

int zone_gc_thread(void *data)
{
	struct zone_sb_info *sbi = data;
	unsigned int zone;

	while (!kthread_should_stop()) {
		if (victim_zone(sbi, &zone)) {
			schedule_timeout_interruptible(HZ);
			continue;
		}
		zone_reset(sbi, zone);
	}
	return 0;
}
