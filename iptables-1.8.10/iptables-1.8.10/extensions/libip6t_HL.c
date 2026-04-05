/* Shared library add-on to ip6tables for the HL match
 *
 * Based on the in-tree hl manpage/tests and the shared ip6t_hl ABI.
 */
#include <stdio.h>
#include <xtables.h>
#include <linux/netfilter_ipv6/ip6t_hl.h>

enum {
	O_HL_EQ = 0,
	O_HL_LT,
	O_HL_GT,
	F_HL_EQ = 1 << O_HL_EQ,
	F_HL_LT = 1 << O_HL_LT,
	F_HL_GT = 1 << O_HL_GT,
	F_ANY   = F_HL_EQ | F_HL_LT | F_HL_GT,
};

#define s struct ip6t_hl_info
static const struct xt_option_entry hl_opts[] = {
	{.name = "hl-eq", .id = O_HL_EQ, .type = XTTYPE_UINT8,
	 .flags = XTOPT_PUT | XTOPT_INVERT, .excl = F_ANY,
	 XTOPT_POINTER(s, hop_limit)},
	{.name = "hl-lt", .id = O_HL_LT, .type = XTTYPE_UINT8,
	 .flags = XTOPT_PUT, .excl = F_ANY,
	 XTOPT_POINTER(s, hop_limit)},
	{.name = "hl-gt", .id = O_HL_GT, .type = XTTYPE_UINT8,
	 .flags = XTOPT_PUT, .excl = F_ANY,
	 XTOPT_POINTER(s, hop_limit)},
	XTOPT_TABLEEND,
};
#undef s

static void hl_help(void)
{
	printf(
"hl match options:\n"
"[!] --hl-eq value          Match when Hop Limit equals value\n"
"    --hl-lt value          Match when Hop Limit is less than value\n"
"    --hl-gt value          Match when Hop Limit is greater than value\n");
}

static void hl_parse(struct xt_option_call *cb)
{
	struct ip6t_hl_info *info = cb->data;

	xtables_option_parse(cb);
	switch (cb->entry->id) {
	case O_HL_EQ:
		info->mode = cb->invert ? IP6T_HL_NE : IP6T_HL_EQ;
		break;
	case O_HL_LT:
		info->mode = IP6T_HL_LT;
		break;
	case O_HL_GT:
		info->mode = IP6T_HL_GT;
		break;
	}
}

static void hl_check(struct xt_fcheck_call *cb)
{
	if (!(cb->xflags & F_ANY))
		xtables_error(PARAMETER_PROBLEM,
			      "hl: one of --hl-eq, --hl-lt, or --hl-gt is required");
}

static void hl_print(const void *ip, const struct xt_entry_match *match,
		     int numeric)
{
	const struct ip6t_hl_info *info = (const void *)match->data;
	const char *op = "==";

	switch (info->mode) {
	case IP6T_HL_NE:
		op = "!=";
		break;
	case IP6T_HL_LT:
		op = "<";
		break;
	case IP6T_HL_GT:
		op = ">";
		break;
	}

	printf(" hl %s %u", op, info->hop_limit);
}

static void hl_save(const void *ip, const struct xt_entry_match *match)
{
	const struct ip6t_hl_info *info = (const void *)match->data;

	switch (info->mode) {
	case IP6T_HL_NE:
		printf(" ! --hl-eq %u", info->hop_limit);
		break;
	case IP6T_HL_EQ:
		printf(" --hl-eq %u", info->hop_limit);
		break;
	case IP6T_HL_LT:
		printf(" --hl-lt %u", info->hop_limit);
		break;
	case IP6T_HL_GT:
		printf(" --hl-gt %u", info->hop_limit);
		break;
	}
}

static int hl_xlate(struct xt_xlate *xl,
		    const struct xt_xlate_mt_params *params)
{
	const struct ip6t_hl_info *info = (const void *)params->match->data;

	xt_xlate_add(xl, "ip6 hoplimit ");
	switch (info->mode) {
	case IP6T_HL_EQ:
		xt_xlate_add(xl, "%u", info->hop_limit);
		break;
	case IP6T_HL_NE:
		xt_xlate_add(xl, "!= %u", info->hop_limit);
		break;
	case IP6T_HL_LT:
		xt_xlate_add(xl, "lt %u", info->hop_limit);
		break;
	case IP6T_HL_GT:
		xt_xlate_add(xl, "gt %u", info->hop_limit);
		break;
	default:
		return 0;
	}

	return 1;
}

static struct xtables_match hl_match = {
	.family		= NFPROTO_IPV6,
	.name		= "hl",
	.version	= XTABLES_VERSION,
	.size		= XT_ALIGN(sizeof(struct ip6t_hl_info)),
	.userspacesize	= XT_ALIGN(sizeof(struct ip6t_hl_info)),
	.help		= hl_help,
	.print		= hl_print,
	.save		= hl_save,
	.x6_parse	= hl_parse,
	.x6_fcheck	= hl_check,
	.x6_options	= hl_opts,
	.xlate		= hl_xlate,
};

void _init(void)
{
	xtables_register_match(&hl_match);
}
