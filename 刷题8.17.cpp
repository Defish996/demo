// leetcode 209. 长度最小的子数组 滑动窗口

class Solution {
public:
    int minSubArrayLen(int target, vector<int>& nums) {
        int n = nums.size();
        if(n == 0) return 0;
        int ans = INT_MAX;// 计算步数
        int start = 0, end = 0;// 窗口边界
        int sum = 0;// 与target进行比较
        while(end < n)// 窗口右边界严格小于数组边界
        {
            sum += nums[end];
            while(sum >= target)// 加完后, 当大于target时, 进行下个值大小的判断
            {
                ans = min(ans, end - start + 1);// 此时子数组的长度
                sum -= nums[start];// 除去已经判断过的值
                ++start;
            }
            ++end;
        }
        return ans == INT_MAX ? 0 : ans;
    }
};